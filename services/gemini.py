"""Gemini API client wrapper for vision and text generation."""

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from google import genai
from google.genai import types


class GeminiClient:
    """Wrapper for Google Gemini API operations."""

    # Retry configuration for JSON parsing errors
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 2  # seconds (doubles each retry)

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.0,
        max_output_tokens: int = 65536,
        thinking_budget: Optional[int] = None,
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
                response_text[-preview_length:]
                if len(response_text) > preview_length
                else ""
            )

            error_msg = f"Failed to parse JSON response"
            if context:
                error_msg += f" ({context})"
            error_msg += f"\nOriginal error: {str(e)}"
            error_msg += f"\nResponse start: {start_preview}"
            if end_preview and end_preview != start_preview:
                error_msg += f"\nResponse end: {end_preview}"

            print(error_msg)  # Log for debugging
            raise  # Re-raise as original exception

    def analyze_pdf_with_vision(
        self,
        pdf_path: Path,
        prompt: str,
        response_schema: Optional[dict] = None,
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
        config_kwargs = {
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
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[prompt, uploaded_file],
                    config=generation_config,
                )

                # Parse response with enhanced error messages
                return self._safe_json_parse(
                    response.text, context="PDF vision analysis"
                )

            except json.JSONDecodeError as e:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * attempt
                    time.sleep(delay)
                else:
                    # Final failure - re-raise
                    raise

    def analyze_video_with_transcript(
        self,
        video_url: str,
        prompt: str,
        response_schema: Optional[dict] = None,
        fps: float = 0.5,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
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
        config_kwargs = {
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
        video_metadata_kwargs = {"fps": fps}
        if start_time is not None:
            video_metadata_kwargs["start_offset"] = f"{start_time}s"
        if end_time is not None:
            video_metadata_kwargs["end_offset"] = f"{end_time}s"

        video_metadata = types.VideoMetadata(**video_metadata_kwargs)

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
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=content,
                    config=generation_config,
                )

                # Parse response with enhanced error messages
                return self._safe_json_parse(
                    response.text, context="video transcript analysis"
                )

            except json.JSONDecodeError as e:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * attempt
                    time.sleep(delay)
                else:
                    # Final failure - re-raise
                    raise

    def extract_entities_and_concepts(
        self,
        transcript_data: dict,
        prompt: str,
        response_schema: Optional[dict] = None,
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
        config_kwargs = {
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
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=full_prompt,
                    config=generation_config,
                )

                # Parse response with enhanced error messages
                return self._safe_json_parse(response.text, context="entity extraction")

            except json.JSONDecodeError as e:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * attempt
                    time.sleep(delay)
                else:
                    # Final failure - re-raise
                    raise
