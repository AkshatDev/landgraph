"""Custom exceptions for the pipeline."""


class NoSupportedFormatError(Exception):
    """None of the formats the pipeline can read is available for a dataset."""
