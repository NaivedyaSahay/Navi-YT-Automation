"""
prompter.py
-----------
Master Mythological Prompter Agent.
Expert AI system designed to generate high-retention, cinematic scripts and
corresponding ultra-detailed visual generation prompts for automated
Instagram and Facebook Reels.

Core Objectives:
1. Storytelling Script Generation (Hindi):
   1-minute engaging reel script based on Hindu mythology.
   Includes a powerful hook in the first 3 seconds, a gripping narrative arc,
   and a profound takeaway/life lesson for the audience.
2. Visual Prompter Engine:
   For every scene/segment of the script, generates hyper-detailed, high-quality,
   cinematic visual prompts (tailored for Kling, Runway, Midjourney, FLUX)
   capturing epic mythological aesthetics, dramatic lighting, and deep emotional resonance.

CLI Usage:
    python prompter.py "The curse of Karna"
    python prompter.py                  # Automatically picks an unposted topic
    python prompter.py --json           # Outputs pure JSON
    python prompter.py --save           # Saves prompt pack to prompts/ directory
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests
import config

# Force UTF-8 encoding on Windows terminal output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("prompter")

# ── Master Mythological Prompter Agent System Prompt ──────────────────────────
MASTER_PROMPTER_SYSTEM_PROMPT = """\
Role: You are the ultimate Master Mythological Content Architect, Creative Director, and Senior Scriptwriter specializing in Hindu Itihasa, Puranas, Vedas, and Sanatan Dharma philosophies. Your sole purpose is to conceptualize, write, and prompt high-retention, cinematic, and profoundly moving 1-minute video content (Reels/Shorts) in Hindi, backed by hyper-detailed, world-class visual generation prompts in English.

You prioritize authentic scriptural accuracy, psychological depth, and modern human relevance over generic summaries. Every piece of content must respect the sanctity of the scriptures while capturing the absolute imagination of a modern digital audience.

---

### SECTION 1: NARRATIVE & SCRIPT ENGINE (HINDI)

When generating a script, you must strictly follow this 3-act structure tailored for a 1-minute format (approx. 130–150 words):

1. The Hook (0–5 seconds): 
   - Never start with a generic introduction like "Aaj hum baat karenge..." (Today we will talk about...). 
   - Start directly with a hard-hitting question, a profound paradox, a raw human emotion, or an epic visual statement that arrests the viewer's scroll instantly.
2. The Core Narrative & Mythological Context (5–45 seconds):
   - Dive straight into the story from the Mahabharata, Ramayana, Bhagavad Gita, Upanishads, or Puranas. 
   - Maintain a serious, immersive, and narrative-driven tone. Use rich, evocative, and pure Hindi (with standard conversational flow so it resonates easily with mass audiences).
3. The Human Takeaway / Life Lesson (45–60 seconds):
   - Connect the ancient event directly to modern human struggles (stress, ego, duty, relationships, internal battles). Conclude with a powerful, philosophical punchline that leaves the viewer thinking long after the video ends.

CRITICAL HINDI LINGUISTIC & FACTUAL RULES (STRICTLY ENFORCED):
- Scriptural Accuracy (Zero Hallucination): Historical and mythological events must be 100% faithful to authentic scriptures (Valmiki Ramayana, Vyasa Mahabharata, Bhagavata Purana). NEVER mix up characters or events:
  * In Ramayana: Lakshmana is Rama's younger brother (अनुज / छोटे भाई), NOT elder brother. Meghnad struck Lakshmana with the Shakti weapon (शक्ति बाण). Hanuman brought the Dronagiri Sanjeevani mountain to save Lakshmana's life.
  * In Mahabharata: Karna is Kunti's eldest son (सूर्यपुत्र), elder brother of the Pandavas. Duryodhana made him King of Anga. Parashurama cursed Karna. Bhishma lay on the bed of arrows awaiting Uttarayan.
  * In Shiva Purana: Sati was Daksha's daughter who immolated in the sacrificial fire; Shiva performed the fierce Tandava in cosmic sorrow; Parvati is Sati's rebirth.
- Respectful Honorific Grammar (आदरसूचक शैली): All deities, Avatars, Rishis, and revered figures (Shiva, Rama, Krishna, Hanuman, Sita, Lakshmana, Bhishma, Karna) MUST ALWAYS be addressed with respectful honorific plural pronouns: 'उन्हें', 'उनका', 'उन्होंने' (NEVER use disrespectful singular pronouns like 'उसे' or 'उसका').
- Zero Made-Up Words: Use ONLY genuine, authentic, dictionary-standard Hindi vocabulary in Devanagari script. NEVER invent non-existent gibberish words (e.g., words like 'सनोहार' or 'पतागा' do not exist in Hindi). Use pure standard words like 'सूर्य का तेज', 'अग्नि की लपटें', 'ब्रह्मांड', 'प्रतिज्ञा', 'मर्यादा', 'समर्पण'.
- Flawless Grammatical Agreement: Ensure 100% correct gender, number, and case agreements (e.g., 'उनके अकेलेपन को', NEVER 'उसकी अकेलापन'; 'सती का अपमान हुआ', NEVER 'सती की अपमान की गई'; 'संसार का अंत', NEVER 'संसार की अंत').
- Pristine TTS Phonetics: Write clean, fluid sentences with natural breath pauses (using commas and periods). Avoid tongue-twister contractions or unusual symbol combinations that cause Text-To-Speech engines to mispronounce.

---

### SECTION 2: VISUAL PROMPTING ENGINE (FOR AI VIDEO/IMAGE GENERATION)

For every scene break in the script, you must output an ultra-detailed, cinematic visual prompt in English. These prompts must never look generic or flat. They must adhere to these strict visual rules:

- Art Style & Aesthetic: Cinematic realism, dark fantasy realism, epic mythological grandeur, ancient Indian architecture (Hoysala, Dravidian, or Nagara style details), intricate stone carvings, weathered bronze, glowing golden accents, and spiritual ethereal lighting.
- Lighting & Atmosphere: Volumetric lighting, dramatic chiaroscuro (deep shadows with intense light rays breaking through, like divine intervention), smoke, dust particles floating in golden hour sunbeams, embers, holy fire (Yajna agni), or celestial blue glow.
- Camera & Lens Physics: Ultra-wide epic establishing shots, macro details on textures (tears on a warrior's cheek, intricate weapon engravings, lotus petals in water), anamorphic lens flare, shallow depth of field, dramatic low-angle hero shots to show scale and power. Shot on ARRI Alexa 65 or IMAX camera standards.
- Color Grading: Deep earthy tones, oxidized copper, royal crimsons, rich midnight blues, and blazing sunset golds. Avoid oversaturated or cartoonish AI-looking colors.

---

### SECTION 3: STRICT QUALITY & CULTURAL GUIDELINES

1. Zero Superficiality: Do not recycle common surface-level stories unless you bring a unique, profound philosophical angle to them. Explore lesser-known layers of characters (e.g., Karna’s internal isolation, Shiva as the ultimate ascetic yet a Grihastha, Krishna's detachment during war).
2. Deep Reverence & Devotion: Treat the deities, sages, and epic figures with absolute dignity, grace, and devotion. The visuals must look majestic, awe-inspiring, and divine, never comical, deformed, or disrespectful.
3. Automation Ready: Format your outputs cleanly with distinct separation between:
   - [SCENE NUMBER & TIMESTAMPS]
   - [HINDI VOICE-OVER SCRIPT]
   - [ENGLISH VISUAL GENERATION PROMPT]
   - [AUDIO / SFX SUGGESTIONS]

### Output Structure Required:
You MUST respond with ONLY a valid JSON object matching the following structure:
{
  "reel_title": "<Catchy title in Hindi/English under 60 chars>",
  "target_duration": "~60 seconds",
  "category": "<Mahabharata | Ramayana | Lord Shiva | Lord Krishna | Upanishads | Vedas | Puranas | Karma>",
  "scenes": [
    {
      "scene_number": 1,
      "timestamps": "0–5 seconds",
      "segment_name": "The Hook",
      "hindi_voiceover": "<Spoken Hindi hook, 15-20 words, arresting the scroll instantly>",
      "visual_prompt": "<Ultra-detailed cinematic English prompt matching Section 2 rules, ARRI Alexa 65 standard, dramatic lighting, vertical 9:16>",
      "audio_sfx_suggestions": "<Sound design and SFX suggestions (e.g., deep temple bell resonance, howling cold wind, subtle bass drop)>"
    },
    {
      "scene_number": 2,
      "timestamps": "5–25 seconds",
      "segment_name": "The Core Narrative (Part 1 - The Trial)",
      "hindi_voiceover": "<Spoken Hindi narrative, 35-45 words in rich evocative Hindi>",
      "visual_prompt": "<Ultra-detailed cinematic English prompt capturing mythological grandeur and architectural details, 9:16 vertical>",
      "audio_sfx_suggestions": "<Sound design and SFX suggestions (e.g., heavy battle drums, thunder crack, chariot wheels rumbling)>"
    },
    {
      "scene_number": 3,
      "timestamps": "25–45 seconds",
      "segment_name": "The Core Narrative (Part 2 - The Turning Point)",
      "hindi_voiceover": "<Spoken Hindi climax and turning point, 35-45 words>",
      "visual_prompt": "<Ultra-detailed cinematic English prompt capturing divine intervention, chiaroscuro lighting, 9:16 vertical>",
      "audio_sfx_suggestions": "<Sound design and SFX suggestions (e.g., celestial drone, Sudarshana whirring energy, holy fire crackle)>"
    },
    {
      "scene_number": 4,
      "timestamps": "45–60 seconds",
      "segment_name": "The Human Takeaway / Life Lesson",
      "hindi_voiceover": "<Spoken Hindi philosophical takeaway connecting ancient wisdom to modern human struggles, 30-40 words>",
      "visual_prompt": "<Ultra-detailed cinematic English prompt of serene temple sanctum, sunrise god-rays, 9:16 vertical>",
      "audio_sfx_suggestions": "<Sound design and SFX suggestions (e.g., meditative Tanpura drone, gentle flute notes, dying embers)>"
    }
  ],
  "full_script": "<Full concatenated spoken Hindi story in Devanagari — strictly 130 to 150 words>",
  "fb_reels_caption": "<Compelling Hindi caption with the moral lesson and emojis. Under 300 chars>",
  "ig_reels_caption": "<Engaging Hindi caption with 6-8 relevant hashtags. Under 300 chars>",
  "hashtags": ["#SanatanDharma", "#Mahabharata", "#BhagavadGita", "#HinduMythology", "#LifeLessons", "#Karma", "#SpiritualWisdom"],
  "keywords": ["ancient indian temple", "sacred fire ritual", "himalayas meditation", "golden divine light"]
}
"""


def generate_mythological_prompt_pack(topic: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates a full cinematic script and visual prompt package for a given topic
    using Groq AI (or Gemini fallback), adhering strictly to the Master Mythological Prompter Agent persona.
    """
    # 1. Resolve topic
    if not topic:
        from topic_picker import get_trending_topics
        chosen = get_trending_topics(n=1)
        selected_topic = chosen[0]["topic"] if chosen else "The curse of Karna and true Dharma"
    else:
        selected_topic = topic

    logger.info("Master Mythological Prompter Agent activated for topic: '%s'", selected_topic)

    # 2. Call Groq API
    result_data = None
    if config.GROQ_API_KEY:
        from script_generator import GROQ_MODELS
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        for model in GROQ_MODELS:
            try:
                logger.info("Prompter calling Groq (%s)...", model)
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": MASTER_PROMPTER_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Generate a cinematic reel script and visual prompts for: {selected_topic}"}
                    ],
                    "temperature": 0.75,
                    "max_tokens": 3200,
                    "response_format": {"type": "json_object"},
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=35)
                if resp.status_code == 200:
                    raw = resp.json()["choices"][0]["message"]["content"]
                    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                    raw = re.sub(r"^```(?:json)?", "", raw.strip(), flags=re.IGNORECASE)
                    raw = re.sub(r"```$", "", raw.strip())
                    data = json.loads(raw)
                    if data.get("scenes") and len(data["scenes"]) >= 3:
                        result_data = data
                        break
            except Exception as exc:
                logger.warning("Groq model %s error: %s", model, exc)

    # 3. Fallback to Gemini if Groq failed
    if not result_data and config.GEMINI_API_KEY:
        try:
            logger.info("Prompter calling Gemini fallback...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
            full_prompt = f"{MASTER_PROMPTER_SYSTEM_PROMPT}\n\nGenerate for: {selected_topic}"
            payload = {
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
            }
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
            if resp.status_code == 200:
                raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(raw)
                if data.get("scenes"):
                    result_data = data
        except Exception as exc:
            logger.warning("Gemini prompter fallback error: %s", exc)

    # 4. Built-in Master Prompter Offline Fallback
    if not result_data:
        logger.info("Using built-in master prompter template for: %s", selected_topic)
        result_data = _get_default_prompter_pack(selected_topic)

    # 5. Normalize and adapt fields for downstream video pipeline compatibility
    _normalize_prompter_data(result_data, selected_topic)
    return result_data


def _normalize_prompter_data(data: Dict[str, Any], topic: str) -> None:
    """Ensures consistent fields for both human readability and automated video pipeline."""
    # Ensure full script exists
    scenes = data.get("scenes", [])
    if not data.get("full_script"):
        parts = [s.get("hindi_voiceover", "") for s in scenes]
        data["full_script"] = " ".join([p for p in parts if p]).strip()

    # Clean script for voiceover engine
    script_clean = re.sub(r"\[.*?\]|\(.*?\)", "", data["full_script"])
    script_clean = re.sub(r"\s+", " ", script_clean).strip()
    data["script"] = script_clean
    data["title"] = data.get("reel_title") or data.get("title") or topic

    # Build image_prompts list
    image_prompts = []
    for s in scenes:
        p = s.get("visual_prompt", "")
        if p:
            image_prompts.append(p)
    data["image_prompts"] = image_prompts

    # Calculate word ratios for narrative timing sync
    scene_words = [max(1, len(s.get("hindi_voiceover", "").split())) for s in scenes]
    total_w = sum(scene_words)
    data["scene_ratios"] = [w / total_w for w in scene_words] if total_w > 0 else [0.25, 0.25, 0.25, 0.25]


def _get_default_prompter_pack(topic: str) -> Dict[str, Any]:
    """Default master prompter package for Karna & Dharma."""
    return {
        "reel_title": "कर्ण का पतन और सबसे बड़ी सीख",
        "target_duration": "~60 seconds",
        "category": "Mahabharata",
        "scenes": [
            {
                "scene_number": 1,
                "timestamps": "0–5 seconds",
                "segment_name": "The Hook",
                "hindi_voiceover": "क्या आप जानते हैं कि महाभारत के सबसे शक्तिशाली योद्धा कर्ण का वध केवल एक बाण से नहीं, बल्कि उसके अतीत के कर्मों से हुआ था?",
                "visual_prompt": "Cinematic realism, dark fantasy grandeur, macro detail on warrior Karna's weathered face, dust and tears on his cheek, divine celestial armor glowing with faint golden embers under cracked silk robes, shallow depth of field, dramatic low-angle shot, shot on ARRI Alexa 65, deep earthy tones, oxidized copper armor, vertical 9:16",
                "audio_sfx_suggestions": "Deep resonant temple bell ringing, low ominous bass drone, crackling distant embers"
            },
            {
                "scene_number": 2,
                "timestamps": "5–25 seconds",
                "segment_name": "The Core Narrative (Part 1 - The Trial)",
                "hindi_voiceover": "जब कुरुक्षेत्र में कर्ण के रथ का पहिया भूमि में धंस गया, तब उसने लाचार होकर कृष्ण से धर्म और नियमों की दुहाई दी।",
                "visual_prompt": "Epic mythological grandeur, wide establishing shot of Kurukshetra battlefield at sunset, ancient Indian war chariot with heavy wooden wheels stuck deep in thick crimson mud, smoke and dust particles floating in golden hour sunbeams, dramatic chiaroscuro, IMAX camera standard, vertical 9:16",
                "audio_sfx_suggestions": "Thunderous wooden chariot wheel cracking, heavy battle drums in distance, howling desert wind"
            },
            {
                "scene_number": 3,
                "timestamps": "25–45 seconds",
                "segment_name": "The Core Narrative (Part 2 - The Turning Point)",
                "hindi_voiceover": "इस पर भगवान कृष्ण ने मुस्कुराते हुए पूछा—कर्ण, जब द्रौपदी का भरी सभा में अपमान हो रहा था, तब तुम्हारा धर्म और तुम्हारी नैतिकता कहाँ थी?",
                "visual_prompt": "Cinematic dark fantasy realism, Lord Krishna standing tall on celestial chariot, majestic peacock feather crown, piercing compassionate gaze, chiaroscuro lighting with celestial blue glow and blazing golden sunbeams piercing through dark monsoon thunderclouds, vertical 9:16",
                "audio_sfx_suggestions": "Celestial drone resonance, subtle metallic ring of Sudarshana aura, sacred conch echo"
            },
            {
                "scene_number": 4,
                "timestamps": "45–60 seconds",
                "segment_name": "The Human Takeaway / Life Lesson",
                "hindi_voiceover": "इस कहानी से हम इंसानों को सबसे बड़ी सीख यह मिलती है कि अधर्म और गलत लोगों का साथ हमेशा पतन की ओर ले जाता है। जीवन में सही पक्ष चुनना ही सच्चा धर्म है।",
                "visual_prompt": "Ancient Indian temple sanctum, Hoysala and Dravidian intricate stone carvings, glowing brass oil lamps (diyas) casting warm amber light on wet stone floor, incense smoke swirling in morning sunbeams, serene spiritual atmosphere, shot on ARRI Alexa 65, vertical 9:16",
                "audio_sfx_suggestions": "Harmonic meditative Tanpura drone, gentle flute melody, peaceful crackling holy fire"
            },
        ],
        "full_script": (
            "क्या आप जानते हैं कि महाभारत के सबसे शक्तिशाली योद्धा कर्ण का वध केवल एक बाण से नहीं, "
            "बल्कि उसके अतीत के कर्मों से हुआ था? जब कुरुक्षेत्र में कर्ण के रथ का पहिया भूमि में धंस गया, "
            "तब उसने कृष्ण से धर्म की दुहाई दी। इस पर भगवान कृष्ण ने मुस्कुराते हुए पूछा—कर्ण, जब द्रौपदी का भरी सभा में "
            "अपमान हो रहा था, तब तुम्हारा धर्म कहाँ था? इस कहानी से हम इंसानों को सबसे बड़ी सीख यह मिलती है कि "
            "अधर्म और गलत लोगों का साथ हमेशा पतन की ओर ले जाता है। सनातन ज्ञान के लिए फॉलो ज़रूर करें।"
        ),
        "fb_reels_caption": "🏹 महाभारत से जीवन की सबसे बड़ी सीख! गलत संगति और अधर्म का परिणाम हमेशा विनाशकारी होता है। #Mahabharata #Karma #LifeLessons",
        "ig_reels_caption": "कर्ण के जीवन से इंसान के लिए सबसे बड़ी सीख 🕉️✨ गलत संगति हमेशा पतन लाती है। #Mahabharata #SanatanDharma #Krishna #Karma #LifeLessons",
        "hashtags": ["#Mahabharata", "#SanatanDharma", "#HinduMythology", "#Krishna", "#Karma", "#LifeLessons"],
        "keywords": ["ancient indian temple", "sacred fire ritual", "himalayas meditation", "golden divine light"],
    }


def print_formatted_prompter_pack(pack: Dict[str, Any]) -> None:
    """Prints a beautiful, highly readable output matching the Master Mythological Content Architect format."""
    title = pack.get("reel_title") or pack.get("title", "Mythology Reel")
    duration = pack.get("target_duration", "~60 seconds")
    category = pack.get("category", "Sanatan Dharma")

    print("\n" + "=" * 75)
    print("  🕉️  MASTER MYTHOLOGICAL CONTENT ARCHITECT & PROMPTER AGENT")
    print("=" * 75)
    print(f"🎬 Reel Title:      {title}")
    print(f"⏱️  Target Duration: {duration}")
    print(f"🏷️  Category:        {category}")
    print("-" * 75)

    scenes = pack.get("scenes", [])
    for s in scenes:
        num = s.get("scene_number", 1)
        timestamps = s.get("timestamps", f"Scene {num}")
        seg = s.get("segment_name", "")
        hindi = s.get("hindi_voiceover", "")
        prompt = s.get("visual_prompt", "")
        sfx = s.get("audio_sfx_suggestions", "Dramatic cinematic score and sacred ambiance")

        print(f"\n[SCENE NUMBER & TIMESTAMPS]")
        print(f"Scene {num}: {seg} ({timestamps})")
        print("\n[HINDI VOICE-OVER SCRIPT]")
        print(f"\"{hindi}\"")
        print("\n[ENGLISH VISUAL GENERATION PROMPT]")
        print(f"{prompt}")
        print("\n[AUDIO / SFX SUGGESTIONS]")
        print(f"{sfx}")
        print("-" * 75)

    print("\n📜 FULL SPOKEN SCRIPT (HINDI):")
    print(f"   {pack.get('full_script', pack.get('script', ''))}")
    print("\n📱 INSTAGRAM CAPTION:")
    print(f"   {pack.get('ig_reels_caption', '')}")
    print("=" * 75 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Master Mythological Prompter Agent CLI")
    parser.add_argument("topic", nargs="?", help="Specific topic or story title (e.g. 'The curse of Karna')")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format only")
    parser.add_argument("--save", action="store_true", help="Save prompt pack to prompts/ directory as JSON")
    args = parser.parse_args()

    pack = generate_mythological_prompt_pack(args.topic)

    if args.save:
        out_dir = Path(__file__).parent / "prompts"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w\-]", "_", (args.topic or pack.get("reel_title", "prompt_pack"))[:40])
        file_path = out_dir / f"{safe_name}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(pack, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved prompt pack to: {file_path}")

    if args.json:
        print(json.dumps(pack, indent=2, ensure_ascii=False))
    else:
        print_formatted_prompter_pack(pack)


if __name__ == "__main__":
    main()
