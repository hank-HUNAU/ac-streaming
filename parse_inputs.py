#!/usr/bin/env python3
"""Parse TTS text files into sections and generate section config for batch audio generation."""

import json, os, re, csv, sys

SKILL_DIR = "/root/.codingmatrix/project-tpl/.ai-ready/skills/edge-tts-aligner"
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
sys.path.insert(0, SKILL_DIR)

WORK_DIR = "/workspace/acspeaker"
os.chdir(WORK_DIR)

def slugify(title):
    """Convert section title to snake_case ID."""
    s = title.strip().lower()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s-]+', '_', s)
    return s

def parse_tts_file(ch_num, tts_path):
    """Parse TTS text file into sections."""
    with open(tts_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    sections = []
    for i, para in enumerate(paragraphs):
        lines = para.split('\n')
        first_line = lines[0].strip()
        
        # Extract section title and body
        # Pattern: "Title text. Body text..." or "Title. Body text..."
        body = para
        
        # Try to extract title from first sentence
        title = first_line
        # For numbered sections like "1 Introduction"
        num_match = re.match(r'^(\d+)\s+(.+)', first_line)
        if num_match:
            # Has number prefix
            # Whole first line is title
            pass
        elif '.' in first_line[:60]:
            # First sentence ends at first period
            # But keep the whole title including numbers
            pass
        
        # Generate section ID
        clean_first = first_line.rstrip('.')
        section_id = slugify(clean_first)
        
        # Remove leading number for ID (e.g., "2_in_vivo_effects" → "in_vivo_effects")
        num_prefix = re.match(r'^(\d+)_(.+)', section_id)
        if num_prefix:
            section_id = f"{num_prefix.group(1)}_{num_prefix.group(2)}"
        
        sections.append({
            'id': section_id,
            'title': first_line,
            'text': body,
            'index': i,
            'paragraph_count': len(lines),
            'total_chars': len(body),
        })
    
    return sections

def parse_entities_csv(csv_path):
    """Parse entities CSV file."""
    entities = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entities.append({
                'category': row.get('category', ''),
                'term': row.get('term', ''),
                'normalized_name': row.get('normalized_name', ''),
                'synonyms': row.get('synonyms', ''),
            })
    return entities

def split_sentences(text):
    """Split text into sentences using NLTK if available, else regex."""
    try:
        import nltk
        nltk.data.path.append('/root/nltk_data')
        return nltk.sent_tokenize(text)
    except:
        # Simple regex fallback
        return re.split(r'(?<=[.!?])\s+', text)

def main():
    for ch_num, ch_name in [('01', '01 Grapes and Brain Health'), ('02', '02 Grapes and Atherosclerosis')]:
        print(f"\n{'='*60}")
        print(f"Processing Chapter {ch_num}: {ch_name}")
        print('='*60)
        
        tts_path = os.path.join(WORK_DIR, 'data', f'{ch_name} TTS.txt')
        entities_path = os.path.join(WORK_DIR, 'data', f'{ch_name} entities.txt')
        
        # Parse TTS sections
        sections = parse_tts_file(ch_num, tts_path)
        print(f'Parsed {len(sections)} sections from TTS file')
        
        # Parse entities
        entities = parse_entities_csv(entities_path)
        print(f'Parsed {len(entities)} entities from CSV')
        
        # Generate section ID mapping (preserve section order)
        # Clean up section IDs to be shorter
        section_ids = []
        for i, sec in enumerate(sections):
            sid = sec['id']
            # Shorten very long IDs
            if len(sid) > 40:
                words = sid.split('_')[:5]
                sid = '_'.join(words)
            section_ids.append(f"{i}_{sid}")
            sections[i]['final_id'] = f"{i}_{sid}"
        
        # Save parsed data
        parsed_path = os.path.join(WORK_DIR, 'data', f'ch{ch_num}_parsed.json')
        output = {
            'chapter': ch_num,
            'title': ch_name,
            'sections': sections,
            'entities': entities,
            'entities_count': len(entities),
        }
        with open(parsed_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f'Saved parsed data to {parsed_path}')
        
        # Print section summary
        for sec in sections:
            print(f"  [{sec['final_id']}] {sec['title'][:60]} ({sec['total_chars']} chars)")
        
        # Print entity categories
        cats = {}
        for e in entities:
            c = e['category']
            cats[c] = cats.get(c, 0) + 1
        print(f'  Entity categories: {cats}')

if __name__ == '__main__':
    main()
