"""Gemini API client wrapper for vision and text generation."""

import json
import os
import time
from functools import wraps
from typing import Callable, ParamSpec, TypeVar
from pathlib import Path
from typing import Any, Iterable, cast

from google import genai
from google.genai import types

P = ParamSpec("P")
R = TypeVar("R")


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, max_calls: int = 60, period: float = 60.0) -> None:
        self.max_calls = max_calls
        self.period = period
        self.calls: list[float] = []

    def wait_if_needed(self) -> None:
        now = time.time()
        self.calls = [call_time for call_time in self.calls if now - call_time < self.period]
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self.calls.append(now)


def rate_limit(limiter: RateLimiter) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to apply rate limiting to a function."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            limiter.wait_if_needed()
            return func(*args, **kwargs)

        return wrapper

    return decorator


_rate_limiter = RateLimiter()


class GeminiClient:
    """Wrapper for Google Gemini API operations."""

    # Retry configuration for JSON parsing errors
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 2  # seconds (doubles each retry)

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.0,
        max_output_tokens: int = 65536,
        thinking_budget: int | None = None,
    ):
        """
        Initialize Gemini client.

        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
            model: Model name to use (default: gemini-2.5-flash)
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative, default: 0.0)
            max_output_tokens: Maximum tokens in response (default: 65536 for gemini-2.5-flash)
            thinking_budget: Thinking budget in tokens (0=no thinking, -1=model controls, 1-24576=specific budget, None=default)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY must be provided or set in environment")

        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.thinking_budget = thinking_budget
        self.client = genai.Client(api_key=self.api_key)
        self.usage_log: list[dict[str, Any]] = []

    def _extract_usage(self, response: Any) -> dict[str, int] | None:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            usage = getattr(response, "usage", None)
        if usage is None:
            return None

        if isinstance(usage, dict):
            prompt_tokens = usage.get("prompt_token_count")
            output_tokens = usage.get("candidates_token_count")
            total_tokens = usage.get("total_token_count")
        else:
            prompt_tokens = getattr(usage, "prompt_token_count", None)
            output_tokens = getattr(usage, "candidates_token_count", None)
            total_tokens = getattr(usage, "total_token_count", None)

        if prompt_tokens is None and output_tokens is None and total_tokens is None:
            return None

        return {
            "prompt_tokens": int(prompt_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "total_tokens": int(total_tokens or 0),
        }

    def _record_usage(self, response: Any, stage: str, duration_ms: float) -> None:
        usage = self._extract_usage(response)
        if not usage:
            return
        self.usage_log.append(
            {
                "stage": stage,
                "model": self.model,
                "duration_ms": duration_ms,
                **usage,
            }
        )

    def _safe_json_parse(self, response_text: str, context: str = "") -> dict[str, Any]:
        """
        Parse JSON response with enhanced error messages for debugging.

        Args:
            response_text: Raw JSON string from Gemini API
            context: Context string for error messages (e.g., "entity extraction")

        Returns:
            Parsed JSON dictionary

        Raises:
            json.JSONDecodeError: With enhanced error message showing response preview
        """
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            # Enhance error message with response preview for debugging
            preview_length = 500
            start_preview = response_text[:preview_length]
            end_preview = (
                response_text[-preview_length:] if len(response_text) > preview_length else ""
            )

            error_msg = "Failed to parse JSON response"
            if context:
                error_msg += f" ({context})"
            error_msg += f"\nOriginal error: {str(e)}"
            error_msg += f"\nResponse start: {start_preview}"
            if end_preview and end_preview != start_preview:
                error_msg += f"\nResponse end: {end_preview}"

            print(error_msg)  # Log for debugging
            raise  # Re-raise as original exception

    @rate_limit(_rate_limiter)
    def analyze_pdf_with_vision(
        self,
        pdf_path: Path,
        prompt: str,
        response_schema: dict | None = None,
        stage: str = "pdf_vision",
    ) -> dict[str, Any]:
        """
        Analyze a PDF using Gemini vision with optional structured output.

        Args:
            pdf_path: Path to PDF file
            prompt: Instruction prompt for analysis
            response_schema: Optional JSON schema for structured output

        Returns:
            Parsed JSON response from model
        """
        # Upload the PDF file
        uploaded_file = self.client.files.upload(file=str(pdf_path))

        # Prepare generation config
        config_kwargs: dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        if response_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        # Add thinking config if thinking_budget is specified
        if self.thinking_budget is not None:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=self.thinking_budget,
                include_thoughts=False,  # Don't include thinking in output
            )

        generation_config = types.GenerateContentConfig(**config_kwargs)

        # Retry logic for transient failures
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Generate content
                start_time = time.perf_counter()
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[prompt, uploaded_file],
                    config=generation_config,
                )
                duration_ms = (time.perf_counter() - start_time) * 1000
                self._record_usage(response, stage=stage, duration_ms=duration_ms)

                # Parse response with enhanced error messages
                return self._safe_json_parse(response.text or "", context="PDF vision analysis")

            except json.JSONDecodeError:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * attempt
                    time.sleep(delay)
                else:
                    # Final failure - re-raise
                    raise

        raise RuntimeError("Failed to analyze PDF with Gemini")

    @rate_limit(_rate_limiter)
    def analyze_video_with_transcript(
        self,
        video_url: str,
        prompt: str,
        response_schema: dict | None = None,
        fps: float = 0.5,
        start_time: int | None = None,
        end_time: int | None = None,
        stage: str = "video_transcription",
    ) -> dict[str, Any]:
        """
        Analyze a YouTube video and generate transcript.

        Args:
            video_url: YouTube video URL
            prompt: Instruction prompt for transcription
            response_schema: Optional JSON schema for structured output
            fps: Frames per second to sample (lower = fewer tokens)
            start_time: Optional start time in seconds
            end_time: Optional end time in seconds

        Returns:
            Parsed JSON response from model
        """
        # Prepare generation config
        config_kwargs: dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        if response_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        # Add thinking config if thinking_budget is specified
        if self.thinking_budget is not None:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=self.thinking_budget,
                include_thoughts=False,  # Don't include thinking in output
            )

        generation_config = types.GenerateContentConfig(**config_kwargs)

        # Build video metadata with FPS and optional time segments
        start_offset = f"{start_time}s" if start_time is not None else None
        end_offset = f"{end_time}s" if end_time is not None else None
        video_metadata = types.VideoMetadata(
            fps=fps,
            start_offset=start_offset,
            end_offset=end_offset,
        )

        # Build content with proper structure for YouTube URL
        content = types.Content(
            parts=[
                types.Part(
                    file_data=types.FileData(file_uri=video_url),
                    video_metadata=video_metadata,
                ),
                types.Part(text=prompt),
            ]
        )

        # Retry logic for transient failures
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Generate content
                start_time_perf = time.perf_counter()
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=content,
                    config=generation_config,
                )
                duration_ms = (time.perf_counter() - start_time_perf) * 1000
                self._record_usage(response, stage=stage, duration_ms=duration_ms)

                # Parse response with enhanced error messages
                return self._safe_json_parse(
                    response.text or "", context="video transcript analysis"
                )

            except json.JSONDecodeError:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * attempt
                    time.sleep(delay)
                else:
                    # Final failure - re-raise
                    raise

        raise RuntimeError("Failed to analyze video with Gemini")

    @rate_limit(_rate_limiter)
    def extract_entities_and_concepts(
        self,
        transcript_data: dict,
        prompt: str,
        response_schema: dict | None = None,
        stage: str = "kg_extraction",
    ) -> dict[str, Any]:
        """
        Extract entities and concepts from structured transcript.

        Args:
            transcript_data: Structured transcript data
            prompt: Instruction prompt for entity extraction
            response_schema: Optional JSON schema for structured output

        Returns:
            Parsed JSON response with entities and concepts
        """
        # Convert transcript data to JSON string for context
        transcript_json = json.dumps(transcript_data, indent=2)

        # Prepare generation config
        config_kwargs: dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        if response_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        # Add thinking config if thinking_budget is specified
        if self.thinking_budget is not None:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=self.thinking_budget,
                include_thoughts=False,  # Don't include thinking in output
            )

        generation_config = types.GenerateContentConfig(**config_kwargs)

        # Combine prompt with transcript context
        full_prompt = f"{prompt}\n\nTranscript data:\n{transcript_json}"

        # Retry logic for transient failures
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Generate content
                start_time_perf = time.perf_counter()
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=full_prompt,
                    config=generation_config,
                )
                duration_ms = (time.perf_counter() - start_time_perf) * 1000
                self._record_usage(response, stage=stage, duration_ms=duration_ms)

                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, dict):
                    return parsed

                # Parse response with enhanced error messages
                return self._safe_json_parse(response.text or "", context="entity extraction")

            except json.JSONDecodeError:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * attempt
                    time.sleep(delay)
                else:
                    # Final failure - re-raise
                    raise

        raise RuntimeError("Failed to extract entities with Gemini")

    @rate_limit(_rate_limiter)
    def generate_structured(
        self,
        prompt: str,
        response_schema: dict,
        stage: str = "structured_generation",
    ) -> dict[str, Any]:
        """
        Generate structured output from a prompt using JSON schema.

        Args:
            prompt: Instruction prompt
            response_schema: JSON schema defining the expected output structure
            stage: Stage name for usage tracking

        Returns:
            Parsed JSON response matching the schema
        """
        # Prepare generation config
        config_kwargs: dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "response_mime_type": "application/json",
            "response_schema": response_schema,
        }

        # Add thinking config if thinking_budget is specified
        if self.thinking_budget is not None:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=self.thinking_budget,
                include_thoughts=False,
            )

        generation_config = types.GenerateContentConfig(**config_kwargs)

        # Retry logic for transient failures
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Generate content
                start_time_perf = time.perf_counter()
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=generation_config,
                )
                duration_ms = (time.perf_counter() - start_time_perf) * 1000
                self._record_usage(response, stage=stage, duration_ms=duration_ms)

                # Parse response
                return self._safe_json_parse(response.text or "", context="structured generation")

            except json.JSONDecodeError:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * attempt
                    time.sleep(delay)
                else:
                    raise

        raise RuntimeError("Failed to generate structured output with Gemini")

    @rate_limit(_rate_limiter)
    def embed_texts(
        self,
        texts: list[str],
        model: str | None = None,
        stage: str = "embeddings",
    ) -> list[list[float]]:
        """
        Generate embeddings for text chunks.

        Args:
            texts: List of text strings to embed
            model: Embedding model name (if None, uses v1beta default)

        Returns:
            List of embedding vectors
        """
        if model is None:
            model = "text-embedding-004"  # Default model for v1beta

        start_time_perf = time.perf_counter()
        response = self.client.models.embed_content(
            model=model,
            contents=texts,
        )
        duration_ms = (time.perf_counter() - start_time_perf) * 1000
        self._record_usage(response, stage=stage, duration_ms=duration_ms)

        embeddings: list[list[float]] = []
        raw_embeddings = getattr(response, "embeddings", None)
        if raw_embeddings is None:
            single_embedding = getattr(response, "embedding", None)
            if single_embedding is None:
                raise ValueError("Unexpected embeddings response format")
            return [list(cast(Iterable[float], single_embedding))]

        for item in raw_embeddings:
            values = getattr(item, "values", None)
            if values is None:
                values = getattr(item, "embedding", None)
            if values is None:
                values = item
            if values is None:
                raise ValueError("Unexpected embedding item format")
            embeddings.append(list(cast(Iterable[float], values)))

        return embeddings
