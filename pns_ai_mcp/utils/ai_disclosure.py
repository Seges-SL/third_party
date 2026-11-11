# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""EU AI Act art. 50.2: a machine-readable mark that a file comes from an AI system.

Document properties only; what the reader sees does not change. No imports
from the package: ``controllers/formatters.py`` loads this file by path.
"""

AI_GENERATOR = 'PNS AI Engine'
AI_KEYWORD = 'ai-generated'
AI_DESCRIPTION = 'Generated with an AI system'

HTML_META = (
    '<meta name="generator" content="%s"/><meta name="keywords" content="%s"/>'
    % (AI_GENERATOR, AI_KEYWORD)
)

OOXML_CORE_PART = 'docProps/core.xml'
OOXML_CORE_TYPE = 'application/vnd.openxmlformats-package.core-properties+xml'
OOXML_CORE_REL = (
    'http://schemas.openxmlformats.org/package/2006/relationships/'
    'metadata/core-properties'
)
OOXML_CORE_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<cp:coreProperties '
    'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/">'
    '<dc:creator>%s</dc:creator><cp:keywords>%s</cp:keywords>'
    '<dc:description>%s</dc:description></cp:coreProperties>'
    % (AI_GENERATOR, AI_KEYWORD, AI_DESCRIPTION)
)


def mark_ai_workbook(wb):
    props = wb.properties
    props.creator = AI_GENERATOR
    props.keywords = AI_KEYWORD
    props.description = AI_DESCRIPTION
