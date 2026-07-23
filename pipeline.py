#!/usr/bin/env python3
"""
Full pipeline: parse TTS text → group into sections → batch generate audio + alignment.
Outputs: chptXX_audio/{section_id}.wav, chptXX_audio/{section_id}_alignment.json
         data/chXX/summary.json, data/chXX/sections/{section_id}.json, data/chXX/sections/{section_id}_words.json
"""

import json, os, re, sys, shutil, asyncio
sys.path.insert(0, "/root/.codingmatrix/project-tpl/.ai-ready/skills/edge-tts-aligner/scripts")

from generate import generate
from batch_generate import batch_generate

WORK = "/workspace/acspeaker"
VOICE = "en-US-AriaNeural"
RATE = "+0%"
PITCH = "+0Hz"
ENGINE = "edge-tts"
PARALLEL = 3

def group_sections(raw_sections):
    """
    Group raw paragraphs into logical sections.
    Heuristic: paragraphs separated by "section heading" patterns form new sections.
    A section heading is a short paragraph (<200 chars) that starts a major topic.
    """
    groups = []
    current = None
    
    # Major section heading indicators (title case, no sentence-ending period in first few words)
    major_patterns = [
        r'^Abstract\.',
        r'^Introduction\.',
        r'^In Vivo Effects',
        r'^Mechanism of Action',
        r'^Bioavailability',
        r'^Conclusions?',
        r'^Grape Composition',
        r'^Epidemiological Information',
        r'^Clinical Studies',
        r'^Animal Studies',
        r'^Cell Studies',
        r'^Conclusion\.',
        r'^Endothelial Dysfunction',
        r'^Dyslipidemia',
        r'^Inflammation and Oxidative',
    ]
    
    for sec in raw_sections:
        text = sec['text'].strip()
        title = sec['title'].strip()
        
        is_major = any(re.match(p, title) for p in major_patterns)
        is_very_short = len(text) < 80  # Just a heading, merge with next
        
        if is_major:
            # Start new group
            if current and current['text']:
                groups.append(current)
            current = {'id': sec['final_id'], 'title': title, 'text': text, 'parts': [sec['index']]}
        elif is_very_short and not (text.endswith('.') or text.endswith('!') or text.endswith('?')):
            # Standalone heading - merge into previous or next
            if current:
                current['text'] += ' ' + text
                current['parts'].append(sec['index'])
            else:
                current = {'id': sec['final_id'], 'title': title, 'text': text, 'parts': [sec['index']]}
        elif current:
            current['text'] += '\n\n' + text
            current['parts'].append(sec['index'])
        else:
            current = {'id': sec['final_id'], 'title': title, 'text': text, 'parts': [sec['index']]}
    
    if current and current['text']:
        groups.append(current)
    
    # Assign final IDs: 0_first_major, 1_second_major, etc.
    for i, g in enumerate(groups):
        # Extract clean ID from the first part's ID
        first_part = g['parts'][0]
        if first_part < len(raw_sections):
            raw_id = raw_sections[first_part]['final_id']
            # Simplify: take prefix
            parts = raw_id.split('_')
            if parts[0].isdigit():
                parts = parts[1:]  # Remove index prefix
            clean_id = '_'.join(parts[:3])  # Keep first 3 words
        else:
            clean_id = f"section{i}"
        g['final_id'] = f"{i}_{clean_id}"
    
    return groups

def clean_tts_text(text):
    """Remove metadata patterns that shouldn't be spoken."""
    # Remove page numbers, headers, etc.
    text = re.sub(r'\bPage\s+\d+\b', '', text)
    text = re.sub(r'\b\d{2,}\s*$', '', text, flags=re.MULTILINE)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

async def generate_passage_audio(ch_num, groups, output_dir):
    """Generate TTS audio for each section group."""
    os.makedirs(output_dir, exist_ok=True)
    
    tasks = []
    for g in groups:
        clean_text = clean_tts_text(g['text'])
        if len(clean_text) < 20:
            continue
        tasks.append({
            'id': g['final_id'],
            'text': clean_text,
            'voice': VOICE,
            'engine': ENGINE,
            'rate': RATE,
            'pitch': PITCH,
            'silence_ms': '0',
        })
    
    # Create batch tasks file
    batch_file = os.path.join(WORK, 'data', f'ch{ch_num}_batch_tasks.json')
    with open(batch_file, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    
    print(f"  Generated {len(tasks)} tasks for chapter {ch_num}")
    print(f"  Starting batch generation with parallel={PARALLEL}...")
    
    # Run batch generation
    report = await batch_generate(tasks, output_dir=output_dir, parallel=PARALLEL)
    
    return report, tasks

def split_sentences(text):
    """Split text into sentences."""
    # Simple sentence splitting
    sents = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sents if s.strip()]

def build_section_json(alignment_data, group_info, ch_num):
    """Build section JSON from alignment data."""
    words = alignment_data.get('words', [])
    sentences = alignment_data.get('sentences', [])
    
    return {
        'id': group_info['final_id'],
        'title': group_info['title'],
        'sentences': sentences,
        'sentence_count': len(sentences),
        'word_count': len(words),
        'total_duration': alignment_data.get('total_duration', 0),
        'voice': VOICE,
    }

def build_words_json(alignment_data):
    """Build compact words JSON: [[word, start, end], ...]"""
    words = alignment_data.get('words', [])
    return [[w['text'], w['start'], w['end']] for w in words]

def build_summary_json(ch_num, ch_title, sections_data, groups, entities_data):
    """Build summary.json for a chapter."""
    sections = []
    total_sentences = 0
    total_duration = 0
    
    for i, (g, sec_data) in enumerate(zip(groups, sections_data)):
        if sec_data:
            sections.append({
                'id': g['final_id'],
                'title': g['title'],
                'sentence_count': sec_data.get('sentence_count', 0),
                'word_count': sec_data.get('word_count', 0),
                'duration_s': round(sec_data.get('total_duration', 0), 1),
                'passage_audio_url': f"chpt{ch_num}_audio/{g['final_id']}.mp3",
            })
            total_sentences += sec_data.get('sentence_count', 0)
            total_duration += sec_data.get('total_duration', 0)
    
    return {
        'id': f'ch{ch_num}',
        'title': ch_title,
        'total_sentences': total_sentences,
        'total_duration_s': round(total_duration, 1),
        'total_terms': len(entities_data) if entities_data else 0,
        'total_sections': len(sections),
        'sections': sections,
    }

async def generate_term_audio(ch_num, entities, output_dir):
    """Generate audio for each term."""
    term_dir = os.path.join(output_dir, 'term_audio')
    os.makedirs(term_dir, exist_ok=True)
    
    tasks = []
    for i, e in enumerate(entities):
        term = e['term']
        if not term or len(term) < 2:
            continue
        # Generate audio for the term name
        tid = f"t{i:03d}"
        tasks.append({
            'id': tid,
            'text': term,
            'voice': VOICE,
            'engine': ENGINE,
            'rate': '-15%',  # Slower for clarity
            'pitch': PITCH,
            'silence_ms': '50',
        })
    
    print(f"  Generating {len(tasks)} term audio files...")
    report = await batch_generate(tasks, output_dir=term_dir, parallel=PARALLEL)
    return report

async def process_chapter(ch_num, ch_name):
    """Process one chapter end-to-end."""
    print(f"\n{'='*60}")
    print(f"Processing Chapter {ch_num}: {ch_name}")
    print('='*60)
    
    # Load parsed data
    parsed_path = os.path.join(WORK, 'data', f'ch{ch_num}_parsed.json')
    with open(parsed_path, 'r', encoding='utf-8') as f:
        parsed = json.load(f)
    
    raw_sections = parsed['sections']
    entities = parsed['entities']
    
    # Group into logical sections
    groups = group_sections(raw_sections)
    print(f"  Grouped {len(raw_sections)} paragraphs into {len(groups)} sections")
    for g in groups:
        print(f"    [{g['final_id']}] {g['title'][:50]} ({len(g['text'])} chars)")
    
    # Generate passage audio
    audio_dir = os.path.join(WORK, f'chpt{ch_num}_audio')
    passage_report, tasks = await generate_passage_audio(ch_num, groups, audio_dir)
    
    print(f"  Passage audio: {passage_report['success']}/{passage_report['total']} successful")
    
    # Build section JSONs and summary
    sections_data = []
    sections_dir = os.path.join(WORK, 'data', f'ch{ch_num}', 'sections')
    os.makedirs(sections_dir, exist_ok=True)
    
    for g in groups:
        gid = g['final_id']
        align_path = os.path.join(audio_dir, f'{gid}_alignment.json')
        
        if os.path.exists(align_path):
            with open(align_path, 'r', encoding='utf-8') as f:
                alignment = json.load(f)
            
            sec_json = build_section_json(alignment, g, ch_num)
            words_json = build_words_json(alignment)
            
            # Save section.json
            sec_path = os.path.join(sections_dir, f'{gid}.json')
            with open(sec_path, 'w', encoding='utf-8') as f:
                json.dump(sec_json, f, ensure_ascii=False, indent=2)
            
            # Save words.json
            words_path = os.path.join(sections_dir, f'{gid}_words.json')
            with open(words_path, 'w', encoding='utf-8') as f:
                json.dump(words_json, f, ensure_ascii=False)
            
            sections_data.append(sec_json)
        else:
            sections_data.append(None)
    
    # Build summary.json
    summary = build_summary_json(ch_num, ch_name, sections_data, groups, entities)
    summary_dir = os.path.join(WORK, 'data', f'ch{ch_num}')
    os.makedirs(summary_dir, exist_ok=True)
    summary_path = os.path.join(summary_dir, 'summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"  Summary: {summary['total_sections']} sections, {summary['total_sentences']} sentences, {summary['total_duration_s']:.1f}s")
    
    # Generate term audio
    term_dir = os.path.join(audio_dir, 'term_audio')
    term_report = await generate_term_audio(ch_num, entities, audio_dir)
    print(f"  Term audio: {term_report['success']}/{term_report['total']} successful")
    
    # Save term data
    term_data = []
    for i, e in enumerate(entities):
        tid = f"t{i:03d}"
        term_audio = os.path.join(term_dir, f'{tid}.wav')
        if os.path.exists(term_audio):
            term_data.append({
                'id': i,
                'term_id': tid,
                'term': e['term'],
                'normalized_name': e['normalized_name'],
                'category': e['category'],
                'synonyms': e['synonyms'],
                'audio_file': f'term_audio/{tid}.mp3',
            })
    
    # Save term data to entities.json
    entities_path = os.path.join(summary_dir, 'entities.json')
    with open(entities_path, 'w', encoding='utf-8') as f:
        json.dump(term_data, f, ensure_ascii=False, indent=2)
    
    # Save report
    report = {
        'chapter': ch_num,
        'title': ch_name,
        'passage_groups': len(groups),
        'passage_success': passage_report['success'],
        'passage_errors': passage_report['errors'],
        'term_total': len(entities),
        'term_success': term_report['success'],
        'total_sections': summary['total_sections'],
        'total_sentences': summary['total_sentences'],
        'total_duration_s': summary['total_duration_s'],
    }
    report_path = os.path.join(WORK, 'data', f'ch{ch_num}_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    return report

async def main():
    chapters = [
        ('01', '01 Grapes and Brain Health'),
        ('02', '02 Grapes and Atherosclerosis'),
    ]
    
    all_reports = []
    for ch_num, ch_name in chapters:
        report = await process_chapter(ch_num, ch_name)
        all_reports.append(report)
    
    print(f"\n{'='*60}")
    print("COMPLETE")
    print('='*60)
    for r in all_reports:
        print(f"  Ch{r['chapter']}: {r['passage_success']} passages, {r['term_success']} terms, {r['total_sentences']} sentences, {r['total_duration_s']:.1f}s")

if __name__ == '__main__':
    asyncio.run(main())
