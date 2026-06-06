"""Parse PDF using Reducto API."""

from pathlib import Path
from typing import Any

from ecodev_core import SETTINGS, logger_get
from reducto import Reducto
from reducto.lib.helpers import FullParseResponse, handle_url_response
from reducto.types import EnhanceParam, FormattingParam, ParseResponse

log = logger_get(__name__)

REUCTO_CLIENT = Reducto(api_key=SETTINGS.api_keys.reductoai)


def parse_with_reducto(url: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse PDF using Reducto API and return structured JSON."""
    log.info('Parsing PDF with Reducto')
    local = Path(url)
    if local.exists():
        log.info(f'Uploading local file to Reducto: {local.name}')
        upload = REUCTO_CLIENT.upload(file=local.open('rb'), extension='pdf')
        parsed_response = _reducto_parse(upload)
    else:
        parsed_response = _reducto_parse(url)
    log.info('Resolving parse result (inline body or presigned URL)')
    full_response = handle_url_response(parsed_response)
    usage = full_response.usage
    log.info(f'Reducto usage: {usage.num_pages} pages, {usage.credits} credits — breakdown: {usage.credit_breakdown}')
    return parse_reducto_chunks(full_response, metadata)


def _reducto_parse(input: Any) -> ParseResponse:
    return REUCTO_CLIENT.parse.run(
        input=input,
        retrieval={
            'chunking': {'chunk_mode': 'variable'}
        },
        enhance=EnhanceParam(
            # Use AI to clean up OCR errors in scanned documents.
            agentic=[{'scope': 'text'}],
        ),
        formatting=FormattingParam(
            # Get tables as HTML, md, json, or csv.
            table_output_format='md'
        ),
    )


def parse_reducto_chunks(response: FullParseResponse, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse the chunks from the reducto response (always ResultFullResult after handle_url_response)."""
    all_chunk_data = []
    for chunk in response.result.chunks:
        chunk_data = {'metadata': metadata, 'page_content': chunk.embed}
        all_chunk_data.append(chunk_data)
    return all_chunk_data
