"""
App Spec Validator
==================

Validates app_spec.md structure using standard markdown headers.
Can be used both as a module and as a CLI tool.

Usage:
    from core.spec_validator import validate_spec_content

    result = validate_spec_content(spec_markdown)
    if result['valid']:
        print("Spec is valid!")
    else:
        for error in result['errors']:
            print(f"Error: {error}")
"""

import re
from typing import Dict, List, Any


def validate_headers(content: str, verbose: bool = False) -> tuple[List[str], List[str]]:
    """
    Validate that all required markdown headers are present.

    Args:
        content: The markdown content to validate
        verbose: If True, print additional info during validation

    Returns:
        Tuple of (errors, warnings) - errors is empty if valid
    """
    errors = []
    warnings = []

    # Find all level-2 headers (## Header)
    header_pattern = r'^## (.+)$'
    headers = [m.group(1).strip() for m in re.finditer(header_pattern, content, re.MULTILINE)]

    if verbose:
        print(f"Found {len(headers)} sections: {headers}")

    # Required sections (must have these)
    required = {'Overview', 'Tech Stack', 'Frontend', 'Backend', 'Database'}
    
    # Normalize headers for comparison
    header_lower = {h.lower() for h in headers}
    
    for section in required:
        if section.lower() not in header_lower:
            errors.append(f"Required section '{section}' is missing")

    # Recommended sections (warn if missing)
    recommended = {'Testing', 'Coding Standards', 'Environment Setup'}
    for section in recommended:
        if section.lower() not in header_lower:
            warnings.append(f"Recommended section '{section}' is missing")

    # Check for duplicate headers
    seen = set()
    for header in headers:
        header_lower_single = header.lower()
        if header_lower_single in seen:
            warnings.append(f"Duplicate section: '{header}'")
        seen.add(header_lower_single)

    return errors, warnings


def get_section_summary(content: str) -> List[Dict[str, str]]:
    """
    Extract summary of all sections from markdown headers.

    Args:
        content: The markdown content to analyze

    Returns:
        List of dicts with section info: name
    """
    header_pattern = r'^## (.+)$'
    sections = []

    for match in re.finditer(header_pattern, content, re.MULTILINE):
        name = match.group(1).strip()
        sections.append({'name': name})

    return sections


def validate_spec_content(content: str) -> Dict[str, Any]:
    """
    Validate spec content and return structured result.

    Args:
        content: The markdown content to validate

    Returns:
        Dict with keys:
            - valid: bool - True if no errors
            - errors: List[str] - Error messages
            - warnings: List[str] - Warning messages
            - sections: List[Dict] - Section metadata
    """
    errors, warnings = validate_headers(content)
    sections = get_section_summary(content)

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'sections': sections
    }


def extract_section(content: str, section_name: str) -> str:
    """
    Extract a section's content by header name.

    Args:
        content: The full markdown content
        section_name: Name of section to extract (e.g., 'Backend')

    Returns:
        The content between the header and the next same-level header, or empty string if not found
    """
    # Find the header
    pattern = rf'^## {re.escape(section_name)}\s*$'
    match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
    
    if not match:
        return ''
    
    start = match.end()
    
    # Find next ## header or end of content
    next_header = re.search(r'^## ', content[start:], re.MULTILINE)
    if next_header:
        end = start + next_header.start()
    else:
        end = len(content)
    
    return content[start:end].strip()


# Keep old function names as aliases for backward compatibility
validate_markers = validate_headers
