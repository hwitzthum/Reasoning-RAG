#!/usr/bin/env python3
"""Seed test data into the database.

Loads test document fixtures and creates documents, sections, and paragraphs
in the database for testing and development.

Usage:
    python scripts/seed_test_data.py
"""

import asyncio
import hashlib
import sys
import uuid
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.storage.database import AsyncSessionLocal
from app.storage.models import Document, Section, Paragraph


# Sample test document content
SAMPLE_POLICY_MARKDOWN = """# ICT Security Policy

## 1. Introduction

This document defines the ICT security policies and procedures for Caritas Switzerland.
All employees must adhere to these requirements.

### 1.1 Purpose

The purpose of this policy is to establish security standards for information systems
and data protection throughout the organization.

### 1.2 Scope

This policy applies to all employees, contractors, and third-party vendors who have
access to Caritas systems and data.

## 2. Password Requirements

All user accounts must follow these password requirements:

- Minimum length: 12 characters
- Must contain uppercase and lowercase letters
- Must contain at least one number
- Must contain at least one special character
- Password expiration: 90 days
- Password history: Cannot reuse last 5 passwords

## 3. Access Control

Access to systems and data is granted based on the principle of least privilege.

### 3.1 User Roles

The following user roles are defined:

- **Administrator**: Full system access and configuration rights
- **Editor**: Can create and modify content
- **Viewer**: Read-only access to approved content

### 3.2 Access Review

Access rights must be reviewed quarterly by department managers.
Terminated employees must have access revoked within 24 hours.

## 4. Data Classification

All data must be classified according to sensitivity:

1. **Public**: No restrictions
2. **Internal**: For internal use only
3. **Confidential**: Restricted access, requires authorization
4. **Secret**: Highest protection, encrypted at rest and in transit

## Appendix A: Contact Information

For security incidents, contact the IT Security team:

- Email: security@caritas.ch
- Phone: +41 XX XXX XX XX
- Emergency hotline: Available 24/7

See Section 2 for password requirements. Refer to Section 3.1 for user role definitions.
"""

SAMPLE_POLICY_DE_MARKDOWN = """# IT-Sicherheitsrichtlinie

## 1. Einführung

Dieses Dokument definiert die IT-Sicherheitsrichtlinien für Caritas Schweiz.

### 1.1 Zweck

Der Zweck dieser Richtlinie ist die Festlegung von Sicherheitsstandards.

### 1.2 Geltungsbereich

Diese Richtlinie gilt für alle Mitarbeiter und Vertragspartner.

## 2. Passwortanforderungen

Alle Benutzerkonten müssen diese Passwortanforderungen erfüllen:

- Mindestlänge: 12 Zeichen
- Gross- und Kleinbuchstaben erforderlich
- Mindestens eine Zahl
- Mindestens ein Sonderzeichen

## 3. Zugangskontrolle

Der Zugriff basiert auf dem Prinzip der geringsten Rechte.

Siehe Abschnitt 2 für Passwortanforderungen. Gemäss Anhang A für Kontaktinformationen.
"""


async def create_test_document(
    session,
    doc_id: str,
    title: str,
    markdown: str,
    language: str,
    file_type: str = "pdf",
) -> None:
    """Create a test document with sections and paragraphs."""
    # Generate file hash
    file_hash = hashlib.sha256(markdown.encode()).hexdigest()

    # Parse markdown structure (simplified for testing)
    sections_data = []
    paragraphs_data = []

    current_section = None
    current_section_id = None
    heading_counters = [0, 0, 0]  # For h1, h2, h3

    lines = markdown.split("\n")
    para_index = 0

    for line_num, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Detect headings
        if line.startswith("#"):
            heading_level = len(line.split()[0])  # Count #'s
            heading_text = line.lstrip("#").strip()

            # Update counters
            if heading_level == 1:
                heading_counters[0] += 1
                heading_counters[1] = 0
                heading_counters[2] = 0
                section_id = f"s{heading_counters[0]:03d}"
            elif heading_level == 2:
                heading_counters[1] += 1
                heading_counters[2] = 0
                section_id = f"s{heading_counters[0]:03d}.{heading_counters[1]}"
            else:  # heading_level == 3
                heading_counters[2] += 1
                section_id = (
                    f"s{heading_counters[0]:03d}.{heading_counters[1]}.{heading_counters[2]}"
                )

            # Create section
            sections_data.append(
                {
                    "section_id": section_id,
                    "title": heading_text,
                    "heading_level": heading_level,
                    "summary": f"Section about {heading_text.lower()}",
                    "page_start": line_num // 20 + 1,  # Approximate pages
                    "page_end": line_num // 20 + 1,
                }
            )

            current_section_id = section_id
            para_index = 0

        elif current_section_id and line and not line.startswith("#"):
            # Create paragraph
            para_index += 1
            para_id = f"{doc_id}:{current_section_id}:p{para_index:03d}"
            paragraphs_data.append(
                {
                    "para_id": para_id,
                    "section_id": current_section_id,
                    "para_index": para_index,
                    "text": line,
                    "markdown_source": line,
                    "page_number": line_num // 20 + 1,
                    "section_path": [current_section_id],
                }
            )

    # Create simple ToC JSON
    toc_json = {
        "root": [
            {
                "node_id": s["section_id"],
                "title": s["title"],
                "summary": s["summary"],
                "page_range": [s["page_start"], s["page_end"]],
                "paragraph_count": sum(
                    1 for p in paragraphs_data if p["section_id"] == s["section_id"]
                ),
                "sub_nodes": [],
            }
            for s in sections_data
            if s["heading_level"] == 1
        ]
    }

    # Create document
    document = Document(
        doc_id=doc_id,
        title=title,
        file_type=file_type,
        language=language,
        total_pages=len(lines) // 20 + 1,
        file_hash=file_hash,
        toc_json=toc_json,
        summary=f"Test document: {title}",
        original_filename=f"{title.lower().replace(' ', '_')}.{file_type}",
    )

    # Create sections
    sections = [
        Section(
            doc_id=doc_id,
            section_id=s["section_id"],
            title=s["title"],
            summary=s["summary"],
            page_start=s["page_start"],
            page_end=s["page_end"],
            heading_level=s["heading_level"],
            section_path=[s["section_id"]],
        )
        for s in sections_data
    ]

    # Create paragraphs
    paragraphs = [
        Paragraph(
            para_id=p["para_id"],
            doc_id=doc_id,
            section_id=p["section_id"],
            para_index=p["para_index"],
            text=p["text"],
            markdown_source=p["markdown_source"],
            page_number=p["page_number"],
            section_path=p["section_path"],
        )
        for p in paragraphs_data
    ]

    # Add to database
    session.add(document)
    session.add_all(sections)
    session.add_all(paragraphs)


async def main() -> None:
    """Seed test data into the database."""
    print("Reasoning-RAG Test Data Seeder")
    print("=" * 50)

    async with AsyncSessionLocal() as session:
        # Check if data already exists
        existing_docs = await session.execute("SELECT COUNT(*) FROM documents")
        count = existing_docs.scalar()

        if count > 0:
            print(f"\nDatabase already contains {count} document(s).")
            response = input("Add test documents anyway? (y/N): ")
            if response.lower() != "y":
                print("Seeding cancelled.")
                return

        print("\nCreating test documents...")

        try:
            # Create English test document
            doc_id_en = str(uuid.uuid4())[:12]
            await create_test_document(
                session,
                doc_id=doc_id_en,
                title="ICT Security Policy",
                markdown=SAMPLE_POLICY_MARKDOWN,
                language="en",
                file_type="pdf",
            )
            print(f"  ✓ Created: ICT Security Policy (EN) [{doc_id_en}]")

            # Create German test document
            doc_id_de = str(uuid.uuid4())[:12]
            await create_test_document(
                session,
                doc_id=doc_id_de,
                title="IT-Sicherheitsrichtlinie",
                markdown=SAMPLE_POLICY_DE_MARKDOWN,
                language="de",
                file_type="pdf",
            )
            print(f"  ✓ Created: IT-Sicherheitsrichtlinie (DE) [{doc_id_de}]")

            # Commit changes
            await session.commit()

            # Count inserted records
            result = await session.execute("SELECT COUNT(*) FROM documents")
            doc_count = result.scalar()
            result = await session.execute("SELECT COUNT(*) FROM sections")
            section_count = result.scalar()
            result = await session.execute("SELECT COUNT(*) FROM paragraphs")
            para_count = result.scalar()

            print("\nSeeding complete!")
            print(f"  Documents: {doc_count}")
            print(f"  Sections: {section_count}")
            print(f"  Paragraphs: {para_count}")

            print("\nTest documents are now available for querying.")
            print("Try queries like:")
            print('  - "What are the password requirements?"')
            print('  - "Was sind die Passwortanforderungen?"')
            print('  - "What user roles are defined?"')

        except Exception as e:
            print(f"\n✗ Error during seeding: {e}", file=sys.stderr)
            await session.rollback()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
