import os
import json
import logging
import asyncio
import torch
import re
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
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True
        )
        
        _llm_pipeline = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=150,
            temperature=0.0,
            do_sample=False,
            truncation=True
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

    MAX_INPUT_CHARS = 500
    text = text[:MAX_INPUT_CHARS]

    # Simple pre-filter for performance boost
    text_lower = text.lower()
    
    if any(kw in text_lower for kw in ["bijli", "power"]):
        logger.info({"fast_path": True, "category": "Electricity"})
        return {"category": "Electricity", "problem": "Power Issue", "district": None, "urgency": "medium", "language": "unknown", "confidence": 0.8}
    if any(kw in text_lower for kw in ["pani", "water"]):
        logger.info({"fast_path": True, "category": "Water"})
        return {"category": "Water", "problem": "Water Supply Issue", "district": None, "urgency": "medium", "language": "unknown", "confidence": 0.8}
    if any(kw in text_lower for kw in ["police", "fir", "chori"]):
        logger.info({"fast_path": True, "category": "Police"})
        return {"category": "Police", "problem": "Police Complaint", "district": None, "urgency": "high", "language": "unknown", "confidence": 0.8}
    if any(kw in text_lower for kw in ["road", "sadak", "transport"]):
        logger.info({"fast_path": True, "category": "Transport"})
        return {"category": "Transport", "problem": "Transport Issue", "district": None, "urgency": "medium", "language": "unknown", "confidence": 0.8}

    if retry_count > 0:
        prompt = f"""{SYSTEM_PROMPT}

IMPORTANT: Ensure output is strictly valid JSON.

User Complaint:
{text}

Output:
"""
    else:
        prompt = f"""{SYSTEM_PROMPT}

User Complaint:
{text}

Output:
"""
    
    try:
        def _run_inference():
            with torch.no_grad():
                return llm(prompt, max_new_tokens=150, return_full_text=False)
                
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        outputs = await asyncio.wait_for(
            loop.run_in_executor(None, _run_inference),
            timeout=3.0
        )
        content = outputs[0]["generated_text"].strip()

        # Clean potential markdown wrapping
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0]
            content = content.strip()
            
        if content.startswith("json"):
            content = content[4:].strip()

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            content = match.group()
        else:
            raise json.JSONDecodeError("Invalid JSON structure", content, 0)

        result = json.loads(content)

        # Strict validation
        category = result.get("category", "Other")
        if category not in {"Electricity", "Police", "Water", "Transport", "Land", "Other"}:
            category = "Other"
            
        urgency = result.get("urgency", "low")
        if urgency not in {"low", "medium", "high"}:
            urgency = "low"
            
        confidence = float(result.get("confidence", 0.0))
        if category == "Other":
            confidence *= 0.7
        if result.get("district") is None:
            confidence *= 0.8
            
        confidence = max(0.0, min(1.0, confidence))
            
        logger.info({
            "llm_used": True,
            "confidence": confidence,
            "category": category
        })
            
        return {
            "category": category,
            "problem": result.get("problem", "Unknown Issue"),
            "district": result.get("district", None),
            "urgency": urgency,
            "language": result.get("language", "unknown"),
            "confidence": confidence,
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

def warmup_model():
    """Ensures model loads at startup (important for Render cold start)."""
    get_llm()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(extract_complaint_semantics("test input"))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(extract_complaint_semantics("test input"))
