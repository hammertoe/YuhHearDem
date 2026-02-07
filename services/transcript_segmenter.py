"""Transcript segmentation utilities."""

from dataclasses import dataclass

from parsers.transcript_models import SessionTranscript


@dataclass
class TranscriptSegmentData:
    """Segment metadata for transcript embedding."""

    segment_id: str
    agenda_item_index: int
    speech_block_index: int
    segment_index: int
    speaker_id: str | None
    start_time_seconds: int | None
    end_time_seconds: int | None
    text: str
    sentence_indices: list[int]


class TranscriptSegmenter:
    """Adaptive transcript segmenter for vector search."""

    def __init__(
        self,
        max_chars: int = 800,
        max_sentences: int = 1,
        min_sentences: int = 1,
    ) -> None:
        self.max_chars = max_chars
        self.max_sentences = max_sentences
        self.min_sentences = min_sentences

    def segment(self, transcript: SessionTranscript) -> list[TranscriptSegmentData]:
        segments: list[TranscriptSegmentData] = []

        for agenda_idx, agenda in enumerate(transcript.agenda_items):
            for block_idx, speech in enumerate(agenda.speech_blocks or []):
                buffer: list[str] = []
                sentence_indices: list[int] = []
                segment_index = 0
                start_time = None
                end_time = None

                for sentence_idx, sentence in enumerate(speech.sentences or []):
                    if start_time is None:
                        start_time = self._parse_timecode(sentence.start_time)
                    end_time = self._parse_timecode(sentence.start_time)

                    buffer.append(sentence.text.strip())
                    sentence_indices.append(sentence_idx)

                    current_text = " ".join(buffer).strip()
                    if self._should_flush(current_text, len(sentence_indices)):
                        segments.append(
                            TranscriptSegmentData(
                                segment_id=f"a{agenda_idx}-b{block_idx}-seg{segment_index}",
                                agenda_item_index=agenda_idx,
                                speech_block_index=block_idx,
                                segment_index=segment_index,
                                speaker_id=speech.speaker_id,
                                start_time_seconds=start_time,
                                end_time_seconds=end_time,
                                text=current_text,
                                sentence_indices=list(sentence_indices),
                            )
                        )
                        segment_index += 1
                        buffer = []
                        sentence_indices = []
                        start_time = None
                        end_time = None

                if buffer:
                    segments.append(
                        TranscriptSegmentData(
                            segment_id=f"a{agenda_idx}-b{block_idx}-seg{segment_index}",
                            agenda_item_index=agenda_idx,
                            speech_block_index=block_idx,
                            segment_index=segment_index,
                            speaker_id=speech.speaker_id,
                            start_time_seconds=start_time,
                            end_time_seconds=end_time,
                            text=" ".join(buffer).strip(),
                            sentence_indices=list(sentence_indices),
                        )
                    )

        return segments

    def _should_flush(self, text: str, sentence_count: int) -> bool:
        if sentence_count < self.min_sentences:
            return False
        if sentence_count >= self.max_sentences:
            return True
        return len(text) >= self.max_chars

    def _parse_timecode(self, time_str: str) -> int | None:
        import re

        patterns = [
            r"(\d+)m(\d+)s(\d+)ms",
            r"(\d+)m(\d+)s",
            r"(\d+)s",
            r"PT(\d+)M(\d+)S",
            r"PT(\d+)S",
            r"(\d+):(\d+):(\d+)",
            r"(\d+):(\d+)",
        ]

        for pattern in patterns:
            match = re.match(pattern, time_str)
            if match:
                groups = list(map(int, match.groups()))
                if len(groups) == 3:
                    if pattern.startswith(r"(\d+)m"):
                        minutes, seconds, _ms = groups
                        return minutes * 60 + seconds
                    else:
                        hours, minutes, seconds = groups
                        return hours * 3600 + minutes * 60 + seconds
                elif len(groups) == 2:
                    if pattern.startswith(r"(\d+)m"):
                        minutes, seconds = groups
                        return minutes * 60 + seconds
                    elif pattern.startswith(r"PT(\d+)"):
                        minutes, seconds = groups
                        return minutes * 60 + seconds
                    else:
                        minutes, seconds = groups
                        return minutes * 60 + seconds
                elif len(groups) == 1:
                    return groups[0]
        return None
