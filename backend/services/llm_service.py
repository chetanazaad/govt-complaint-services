import os
import json
import logging
import asyncio
from typing import Optional
from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)

# Very small, fast instruction model optimized for classification and JSON (0.5B parameters)
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

_llm_pipeline = None

def get_llm():
    """Singleton to load the model into memory only once at startup."""
    global _llm_pipeline
    if _llm_pipeline is not None:
        return _llm_pipeline
        
    logger.info(f"Loading local LLM {MODEL_NAME} into memory...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            device_map="cpu",
            low_cpu_mem_usage=True
        )
        
        _llm_pipeline = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=150,
            temperature=0.1,
            do_sample=True,
            top_p=0.9
        )
        logger.info("Local LLM loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load LLM: {e}")
        return None
        
    return _llm_pipeline


SYSTEM_PROMPT = """You are a government complaint understanding system. Convert the input into strict JSON. Do not explain anything.

Required JSON format:
{
"category": "Electricity | Police | Water | Transport | Land | Other",
"problem": "clean normalized issue",
"district": "normalized district or null",
"urgency": "low | medium | high",
"language": "hindi | english | hinglish | unknown",
"confidence": 0.95
}"""


async def extract_complaint_semantics(text: str, retry_count: int = 0) -> dict:
    """
    Call local LLM to extract structured semantics from unstructured raw text.
    Handles English, Hindi, Hinglish, and spelling errors.
    Returns structured JSON with category, problem, district, etc.
    """
    fallback_result = {
        "category": "Other", 
        "problem": "Unknown Issue", 
        "district": None, 
        "urgency": "low", 
        "language": "unknown", 
        "confidence": 0.0
    }
    
    llm = get_llm()
    if not llm:
        return fallback_result

    # Format using chat template explicitly
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text}
    ]
    
    try:
        outputs = llm(messages, max_new_tokens=150, return_full_text=False)
        content = outputs[0]["generated_text"].strip()

        # Clean potential markdown wrapping
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0]
            content = content.strip()
            
        if content.startswith("json"):
            content = content[4:].strip()

        result = json.loads(content)

        # Validate required fields and clamp confidence
        result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
        
        return {
            "category": result.get("category", "Other"),
            "problem": result.get("problem", "Unknown Issue"),
            "district": result.get("district", None),
            "urgency": result.get("urgency", "low"),
            "language": result.get("language", "unknown"),
            "confidence": result["confidence"],
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON (retry={retry_count}): {e}")
        if retry_count < 1:
            return await extract_complaint_semantics(text, retry_count=retry_count + 1)
        return fallback_result
    except Exception as e:
        logger.error(f"LLM extraction service error: {e}")
        return fallback_result


# Maintained for backward compatibility for FastAPI
async def classify_intent(query: str) -> Optional[dict]:
    res = await extract_complaint_semantics(query)
    if res["confidence"] == 0.0:
        return None
    return res
