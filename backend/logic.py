import json
import os

# ==============================================================
# logic.py – simpel GoRules evaluator baseret på Brandklasse_Bestemmelse.json
# ==============================================================

def load_brandtree(path="Brandklasse_Bestemmelse.json"):
    # Hvis stien er relativ, byg den fra projektets rodmappe
    if not os.path.isabs(path):
        # Gå op til rodmappen (backend -> rod)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(root_dir, path)
        if os.path.exists(candidate):
            path = candidate
        else:
            # Fallback to legacy location used earlier
            legacy = os.path.join(root_dir, "frontend", "Brandklasse_Bestemmelse.json")
            path = legacy if os.path.exists(legacy) else candidate
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _resolve_project_path(path: str) -> str:
    """Resolve a path relative to the project root (backend/..)."""
    if os.path.isabs(path):
        return path

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(root_dir, path)
    if os.path.exists(candidate):
        return candidate

    # Fallback to legacy location used earlier
    legacy = os.path.join(root_dir, "frontend", path)
    return legacy if os.path.exists(legacy) else candidate

def load_krav(path="Krav.json"):
    """Load Krav.json decision model"""
    if not os.path.isabs(path):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(root_dir, path)
        if os.path.exists(candidate):
            path = candidate
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# Cache decision models, but allow them to refresh when the underlying JSON files change.
_BRAND_MODEL_CACHE = None
_BRAND_MODEL_PATH = None
_BRAND_MODEL_MTIME = None

KRAV_MODEL = None  # Lazy load when needed


def get_brandtree(path="Brandklasse_Bestemmelse.json"):
    """Return the Brandklasse model.

    Note: Uvicorn's --reload typically only watches .py changes, so JSON edits won't
    automatically reload the process. This function detects mtime changes and reloads
    the JSON model on-demand.
    """
    global _BRAND_MODEL_CACHE, _BRAND_MODEL_PATH, _BRAND_MODEL_MTIME
    resolved = _resolve_project_path(path)
    try:
        mtime = os.path.getmtime(resolved)
    except OSError:
        mtime = None

    if (
        _BRAND_MODEL_CACHE is None
        or _BRAND_MODEL_PATH != resolved
        or (_BRAND_MODEL_MTIME is not None and mtime is not None and mtime != _BRAND_MODEL_MTIME)
    ):
        _BRAND_MODEL_CACHE = load_brandtree(resolved)
        _BRAND_MODEL_PATH = resolved
        _BRAND_MODEL_MTIME = mtime

    return _BRAND_MODEL_CACHE

def _find_node_by_keywords(nodes, keywords):
    """Find a decision node whose name matches any of the keywords (case-insensitive substring)."""
    for name, node in nodes.items():
        n = (name or "").lower()
        for kw in keywords:
            if kw in n:
                return node
    return None

def _parse_first_int(value):
    """Robustly parse the first integer from a value.
    Accepts ints, floats, numeric strings, or comma/whitespace-separated values like "2, 3".
    Returns int on success, else None.
    """
    try:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            s = value.strip().replace("\t", " ").replace("\n", " ")
            # If comma-separated, take the first token
            if "," in s:
                s = s.split(",")[0].strip()
            # Extract first number sequence
            import re
            m = re.search(r"-?\d+", s)
            if m:
                return int(m.group(0))
            # Fallback direct cast
            return int(s)
    except Exception:
        return None
    return None


def _parse_first_number_token(value):
    """Parse the first numeric token from a value and return it as a string.

    Supports integers and decimals (e.g. "1" or "1.1").
    This is used for fields like relevant bilag where "1.1" must not be collapsed to 1.
    Returns None on failure.
    """
    try:
        if isinstance(value, (int, float)):
            # Preserve e.g. 1.0 -> "1" for stable display
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        if isinstance(value, str):
            s = value.strip().replace("\t", " ").replace("\n", " ")
            if "," in s:
                s = s.split(",")[0].strip()
            import re
            m = re.search(r"-?\d+(?:\.\d+)?", s)
            if m:
                tok = m.group(0)
                # Normalize "1.0" -> "1"
                try:
                    n = float(tok)
                    if n.is_integer():
                        return str(int(n))
                except Exception:
                    pass
                return tok
            return None
    except Exception:
        return None
    return None


def _parse_relevant_bilag_token(value):
    """Parse/normalize a relevant bilag token.

    The GoRules models use "1a" and "1b" as the stable identifiers.
    For backwards compatibility we also accept older numeric forms ("1" / "1.1")
    and normalize them into "1a" / "1b".
    """
    try:
        if value is None:
            return None

        # Numeric inputs (legacy)
        if isinstance(value, (int, float)):
            try:
                n = float(value)
                if abs(n - 1.0) < 1e-9:
                    return "1a"
                if abs(n - 1.1) < 1e-9:
                    return "1b"
            except Exception:
                pass
            tok = _parse_first_number_token(value)
            if tok == "1":
                return "1a"
            if tok == "1.1":
                return "1b"
            return tok

        if isinstance(value, str):
            import re
            s = value.strip()
            if s == "":
                return None

            # Unwrap a single surrounding quote-pair (some models store literal quoted strings)
            if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
                s = s[1:-1].strip()

            low = s.lower()

            # Prefer explicit alpha suffix tokens
            if re.search(r"\b1\s*a\b|\b1a\b", low):
                return "1a"
            if re.search(r"\b1\s*b\b|\b1b\b", low):
                return "1b"

            # Legacy numeric forms
            if re.search(r"\b1\.1\b", low):
                return "1b"

            compact = re.sub(r"\s+", "", low)
            if compact in ("1", "1.0"):
                return "1a"
            if compact in ("1.1", "11"):
                return "1b"

            # Fallback: first numeric token if present
            tok = _parse_first_number_token(s)
            if tok == "1":
                return "1a"
            if tok == "1.1":
                return "1b"
            return tok

        return str(value).strip() or None
    except Exception:
        return None


def _normalize_bilag_token_for_compare(token: str):
    """Normalize bilag tokens for equality matching.

    Returns canonical "1a" / "1b" when the input token is a known alias,
    otherwise returns None.
    """
    try:
        if token is None:
            return None
        s = str(token).strip().lower()
        if s == "":
            return None

        # Unwrap a single surrounding quote-pair
        if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
            s = s[1:-1].strip().lower()

        # Only treat exact tokens as aliases (avoid rewriting longer descriptive strings)
        s_compact = s.replace(" ", "")
        if s_compact in ("1", "1a", "1.0"):
            return "1a"
        if s_compact in ("1.1", "11", "1b"):
            return "1b"
        return None
    except Exception:
        return None


def _coerce_number_like(token: str):
    """Coerce a numeric token string to int/float when possible."""
    if token is None:
        return None
    try:
        s = str(token).strip()
        if s == "":
            return None
        if "." in s:
            n = float(s)
            return int(n) if n.is_integer() else n
        return int(s)
    except Exception:
        return None

def evaluate_complete_flow(inputs: dict):
    """
    Evaluerer komplet BR18 flow: Anvendelseskategori -> Risikoklasse -> Brandklasse
    inputs = dict med alle bygningsparametre
    Returnerer dict med alle resultater
    """
    model = get_brandtree()
    # Find alle decision nodes i rækkefølge
    nodes = {node["name"]: node for node in model.get("nodes", []) if node.get("type") == "decisionTableNode"}

    # Resolve core nodes once so we can produce candidates + optimization hints even on early exit.
    ak_node = nodes.get("Anvendelseskategori 2.0") or _find_node_by_keywords(nodes, ["anvendelseskategori"])
    rk_node = nodes.get("Risikoklasse") or _find_node_by_keywords(nodes, ["risikoklasse", "risiko klasse", "risk class"])
    bilag_node = nodes.get("Relevant bilag") or _find_node_by_keywords(nodes, ["relevant bilag", "bilag"])
    bk_node = None
    bk_node_name = None
    for candidate in ("Brandklasse", "Præ-accepterede løsninger"):
        if candidate in nodes:
            bk_node = nodes.get(candidate)
            bk_node_name = candidate
            break
    if bk_node is None:
        bk_node = _find_node_by_keywords(nodes, ["brandklasse", "præ-accepterede", "prae-accepterede"])
        bk_node_name = bk_node.get("name") if bk_node else None
    
    results = {
        "success": True,
        "anvendelseskategori": None,
        "risikoklasse": None,
        "relevant_bilag": None,
        "brandklasse": None,
        "errors": []
    }
    
    current_data = inputs.copy()

    # Backwards compatible aliasing: frontend havde tidligere andre feltnavne end GoRules-modellen.
    # Brandklasse-node forventer bl.a.: fritliggende_BA, med_tilbygning, med_erhvervssammenbygning,
    # antal_fravigelser_fra_praeaccepterede (og evt. andre felter afhængigt af modellen).
    if "fritliggende_BA" not in current_data and "fritstaaende" in current_data:
        current_data["fritliggende_BA"] = current_data.get("fritstaaende")
    if "med_tilbygning" not in current_data and "tilbygning" in current_data:
        current_data["med_tilbygning"] = current_data.get("tilbygning")

    # Normaliser strengfelter vi matcher på (trim og lower-case for robusthed)
    if isinstance(current_data.get("bygningstype"), str):
        current_data["bygningstype"] = current_data["bygningstype"].strip().lower()
    
    # Step 1: Anvendelseskategori
    if ak_node:
        result = evaluate_decision_node(ak_node, current_data)
        if result:
            anvendelseskategori = _parse_first_int(result["value"]) if result.get("value") is not None else None
            results["anvendelseskategori"] = {
                "value": anvendelseskategori,
                "description": result["description"],
                "matched_rule_id": result.get("_matched_rule_id")
            }
            current_data["anvendelseskategori"] = anvendelseskategori
        else:
            # Debug info when AK has no match
            results["debug_ak"] = {
                "inputs_present": list(current_data.keys())
            }
            results["missing_inputs"] = diagnose_missing_inputs_for_node(ak_node, current_data)
            # Even if AK can't be determined yet, we can still provide candidate outputs
            # for downstream nodes, typically with "mangler: anvendelseskategori" etc.
            results["candidates"] = {
                "anvendelseskategori": diagnose_possible_outputs_for_node(ak_node, current_data, output_field="anvendelseskategori"),
                "risikoklasse": diagnose_possible_outputs_for_node(rk_node, current_data, output_field="risikoklasse") if rk_node else [],
                "relevant_bilag": diagnose_possible_outputs_for_node(bilag_node, current_data, output_field="relevant_bilag") if bilag_node else [],
                "brandklasse": diagnose_possible_outputs_for_node(bk_node, current_data, output_field="brandklasse") if bk_node else [],
            }

            results["suggestions"] = {
                "risikoklasse": diagnose_optimization_suggestions_for_node(
                    rk_node,
                    current_data,
                    output_field="risikoklasse",
                    current_value=None,
                    limit=3,
                )
                if rk_node
                else [],
                "brandklasse": diagnose_optimization_suggestions_for_node(
                    bk_node,
                    current_data,
                    output_field="brandklasse",
                    current_value=None,
                    limit=3,
                    # Avoid noisy suggestions that require huge numeric changes.
                    max_numeric_delta_abs=500.0,
                )
                if bk_node
                else [],
            }
            results["success"] = False
            results["errors"].append("No matching rule for Anvendelseskategori")
            return results
    
    # Step 2: Risikoklasse
    if rk_node:
        result = evaluate_decision_node(rk_node, current_data)
        if result:
            risikoklasse = _parse_first_int(result["value"]) if result.get("value") is not None else None
            results["risikoklasse"] = {
                "value": risikoklasse,
                "description": result["description"],
                "matched_rule_id": result.get("_matched_rule_id")
            }
            current_data["risikoklasse"] = risikoklasse
        else:
            results["debug_rk"] = {
                "inputs_present": list(current_data.keys()),
                "anvendelseskategori": current_data.get("anvendelseskategori")
            }
            results["missing_inputs"] = diagnose_missing_inputs_for_node(rk_node, current_data)
            results["candidates"] = {
                "risikoklasse": diagnose_possible_outputs_for_node(rk_node, current_data, output_field="risikoklasse"),
                "relevant_bilag": diagnose_possible_outputs_for_node(bilag_node, current_data, output_field="relevant_bilag") if bilag_node else [],
            }

            results["suggestions"] = {
                "risikoklasse": diagnose_optimization_suggestions_for_node(
                    rk_node,
                    current_data,
                    output_field="risikoklasse",
                    current_value=None,
                    limit=3,
                )
                if rk_node
                else []
            }
            results["success"] = False
            results["errors"].append("No matching rule for Risikoklasse")
            return results
    
    # Step 3: Relevant bilag
    if bilag_node:
        result = evaluate_decision_node(bilag_node, current_data)
        if result:
            # The model can output multiple fields (e.g. relevant_bilag + Bilagsinformation).
            # In that case, evaluate_decision_node won't set result["value"], so read the field explicitly.
            relevant_raw = result.get("relevant_bilag") if isinstance(result, dict) else None
            if relevant_raw is None:
                relevant_raw = result.get("value") if isinstance(result, dict) else None
            relevant_token = _parse_relevant_bilag_token(relevant_raw) if relevant_raw is not None else None
            # Keep output structure consistent with other steps (value + matched_rule_id)
            # so the frontend can treat it like the other result objects.
            results["relevant_bilag"] = {
                "value": relevant_token,
                "description": "",
                "matched_rule_id": result.get("_matched_rule_id"),
            }
            # Backwards-compatible field preserved for older frontend code.
            results["relevant_bilag_matched_rule_id"] = result.get("_matched_rule_id")
            # Keep as string: the GoRules models use "1a"/"1b".
            current_data["relevant_bilag"] = relevant_token

            # Optional: forward any bilag text info if present
            bilagsinfo = result.get("Bilagsinformation") if isinstance(result, dict) else None
            if bilagsinfo not in (None, "", [], {}):
                results["bilagsinformation"] = bilagsinfo
                try:
                    # Prefer to surface bilag info on the relevant_bilag object when possible.
                    if isinstance(results.get("relevant_bilag"), dict):
                        results["relevant_bilag"]["description"] = str(bilagsinfo)
                except Exception:
                    pass

            # Optional: forward bilag title (added to GoRules model as output field 'bilag_titel')
            bilag_titel = result.get("bilag_titel") if isinstance(result, dict) else None
            if bilag_titel not in (None, "", [], {}):
                results["bilag_titel"] = {
                    "value": bilag_titel,
                    "matched_rule_id": result.get("_matched_rule_id"),
                }
        else:
            # Relevant bilag er optional - fortsæt hvis ikke fundet
            results["debug_bilag"] = {
                "inputs_present": list(current_data.keys()),
                "anvendelseskategori": current_data.get("anvendelseskategori"),
                "risikoklasse": current_data.get("risikoklasse")
            }
            # Provide guidance anyway, since brandklasse depends on relevant_bilag.
            results.setdefault("missing_inputs", [])
            results["missing_inputs"] = (results.get("missing_inputs") or []) + diagnose_missing_inputs_for_node(bilag_node, current_data)
            results.setdefault("candidates", {})
            results["candidates"]["relevant_bilag"] = diagnose_possible_outputs_for_node(
                bilag_node,
                current_data,
                output_field="relevant_bilag",
            )
    
    # Step 4: Brandklasse
    # Brandklasse is determined by the resolved brandklasse decision table (e.g. "Brandklasse").
    # Earlier versions used other names (e.g. "Præ-accepterede løsninger"), so we resolve it above.
    bilag_num = current_data.get("relevant_bilag")

    if not bk_node:
        results.setdefault("debug_bk", {})
        results["debug_bk"] = {
            "bilag_node_searched": bk_node_name,
            "available_nodes": list(nodes.keys()),
        }
        results["errors"].append("Brandklasse node not found")
    else:
        result = evaluate_decision_node(bk_node, current_data)
        if result:
            # The output field is "brandklasse"
            brandklasse_value = result.get("brandklasse") if isinstance(result, dict) else None
            results["brandklasse"] = brandklasse_value
            results["brandklasse_matched_rule_id"] = result.get("_matched_rule_id")
            brandklasse_val = result.get("brandklasse")
            brandklasse = _parse_first_int(brandklasse_val) if brandklasse_val is not None else None

            # Extract description from _description field if present
            description = result.get("_description", "")
            if not description and isinstance(result, dict):
                # Try to build a meaningful description from available outputs
                description = f"Brandklasse {brandklasse}" if brandklasse else "Kræver brandrådgivers vurdering"

            # If the updated Brandklasse-model outputs a 'krav' field, surface it directly.
            # This is used e.g. when BK2 is only valid under a specific condition (sprinkling, etc.).
            krav_out = None
            if isinstance(result, dict):
                # Some models output this as 'krav' and others as 'Krav'
                krav_out = result.get("krav") if "krav" in result else result.get("Krav")
            if krav_out not in (None, "", [], {}):
                try:
                    if isinstance(krav_out, (list, tuple)):
                        krav_text = "; ".join([str(x) for x in krav_out if str(x).strip()])
                    else:
                        krav_text = str(krav_out)
                    krav_text = krav_text.strip()
                except Exception:
                    krav_text = ""

                if krav_text:
                    if description:
                        description = f"{description} (Forudsætter: {krav_text})"
                    else:
                        description = f"Brandklasse {brandklasse} (Forudsætter: {krav_text})" if brandklasse else f"Forudsætter: {krav_text}"

            results["brandklasse"] = {
                "value": brandklasse,
                "description": description,
                "matched_rule_id": result.get("_matched_rule_id"),
            }

            # Store additional outputs for frontend use
            results["bilag_outputs"] = {k: v for k, v in result.items() if k not in ["brandklasse", "_description", "_id"]}
        else:
            results["debug_bk"] = {
                "inputs_present": list(current_data.keys()),
                "relevant_bilag": bilag_num,
                "bilag_node_searched": bk_node_name,
            }
            results["missing_inputs"] = diagnose_missing_inputs_for_node(bk_node, current_data)
            results["candidates"] = {
                "brandklasse": diagnose_possible_outputs_for_node(bk_node, current_data, output_field="brandklasse")
            }

            results["suggestions"] = {
                "brandklasse": diagnose_optimization_suggestions_for_node(
                    bk_node,
                    current_data,
                    output_field="brandklasse",
                    current_value=None,
                    limit=3,
                    max_numeric_delta_abs=500.0,
                )
            }
            results["success"] = False
            results["errors"].append(f"No matching rule in {bk_node_name}")

    # Always-on optimization suggestions (when the current value exists, only suggest lower values)
    try:
        rk_current = None
        if isinstance(results.get("risikoklasse"), dict):
            rk_current = results.get("risikoklasse", {}).get("value")
        bk_current = None
        if isinstance(results.get("brandklasse"), dict):
            bk_current = results.get("brandklasse", {}).get("value")

        results.setdefault("suggestions", {})
        if rk_node and "risikoklasse" not in results["suggestions"]:
            results["suggestions"]["risikoklasse"] = diagnose_optimization_suggestions_for_node(
                rk_node,
                current_data,
                output_field="risikoklasse",
                current_value=_parse_first_int(rk_current) if rk_current is not None else None,
                limit=3,
            )
        if bk_node and "brandklasse" not in results["suggestions"]:
            results["suggestions"]["brandklasse"] = diagnose_optimization_suggestions_for_node(
                bk_node,
                current_data,
                output_field="brandklasse",
                current_value=_parse_first_int(bk_current) if bk_current is not None else None,
                limit=3,
                max_numeric_delta_abs=500.0,
            )
    except Exception:
        pass
    
    return results


def evaluate_basic_flow(inputs: dict):
    """Evaluerer kun de "lette" trin: Anvendelseskategori -> Risikoklasse -> Relevant bilag.

    Bruges til trin 1 i UI, hvor brandklasse (bilag-specifik) håndteres på et senere trin.
    """
    model = get_brandtree()
    nodes = {node["name"]: node for node in model.get("nodes", []) if node.get("type") == "decisionTableNode"}

    results = {
        "success": True,
        "anvendelseskategori": None,
        "risikoklasse": None,
        "relevant_bilag": None,
        "errors": [],
    }

    current_data = inputs.copy()

    # Backwards compatible aliasing
    if "fritliggende_BA" not in current_data and "fritstaaende" in current_data:
        current_data["fritliggende_BA"] = current_data.get("fritstaaende")
    if "med_tilbygning" not in current_data and "tilbygning" in current_data:
        current_data["med_tilbygning"] = current_data.get("tilbygning")

    if isinstance(current_data.get("bygningstype"), str):
        current_data["bygningstype"] = current_data["bygningstype"].strip().lower()

    # Step 1: Anvendelseskategori
    ak_node = nodes.get("Anvendelseskategori 2.0") or _find_node_by_keywords(nodes, ["anvendelseskategori"])
    if not ak_node:
        results["success"] = False
        results["errors"].append("Anvendelseskategori node not found")
        return results

    ak_res = evaluate_decision_node(ak_node, current_data)
    if not ak_res:
        results["success"] = False
        results["errors"].append("No matching rule for Anvendelseskategori")
        results["debug_ak"] = {"inputs_present": list(current_data.keys())}
        results["missing_inputs"] = diagnose_missing_inputs_for_node(ak_node, current_data)
        rk_node_tmp = nodes.get("Risikoklasse") or _find_node_by_keywords(nodes, ["risikoklasse", "risiko klasse", "risk class"])
        bilag_node_tmp = nodes.get("Relevant bilag") or _find_node_by_keywords(nodes, ["relevant bilag", "bilag"])
        results["candidates"] = {
            "anvendelseskategori": diagnose_possible_outputs_for_node(ak_node, current_data, output_field="anvendelseskategori"),
            "risikoklasse": diagnose_possible_outputs_for_node(rk_node_tmp, current_data, output_field="risikoklasse") if rk_node_tmp else [],
            "relevant_bilag": diagnose_possible_outputs_for_node(bilag_node_tmp, current_data, output_field="relevant_bilag") if bilag_node_tmp else [],
        }

        results["suggestions"] = {
            "risikoklasse": diagnose_optimization_suggestions_for_node(
                rk_node_tmp,
                current_data,
                output_field="risikoklasse",
                current_value=None,
                limit=3,
            )
            if rk_node_tmp
            else []
        }
        return results

    anv = _parse_first_int(ak_res["value"]) if ak_res.get("value") is not None else None
    results["anvendelseskategori"] = {
        "value": anv, 
        "description": ak_res["description"],
        "matched_rule_id": ak_res.get("_matched_rule_id")
    }
    current_data["anvendelseskategori"] = anv

    # Step 2: Risikoklasse
    rk_node = nodes.get("Risikoklasse") or _find_node_by_keywords(nodes, ["risikoklasse", "risiko klasse", "risk class"])
    if not rk_node:
        results["success"] = False
        results["errors"].append("Risikoklasse node not found")
        return results

    rk_res = evaluate_decision_node(rk_node, current_data)
    if not rk_res:
        results["success"] = False
        results["errors"].append("No matching rule for Risikoklasse")
        results["debug_rk"] = {"inputs_present": list(current_data.keys()), "anvendelseskategori": current_data.get("anvendelseskategori")}
        results["missing_inputs"] = diagnose_missing_inputs_for_node(rk_node, current_data)
        results["candidates"] = {
            "risikoklasse": diagnose_possible_outputs_for_node(rk_node, current_data, output_field="risikoklasse")
        }
        return results

    rk = _parse_first_int(rk_res["value"]) if rk_res.get("value") is not None else None
    results["risikoklasse"] = {
        "value": rk, 
        "description": rk_res["description"],
        "matched_rule_id": rk_res.get("_matched_rule_id")
    }
    current_data["risikoklasse"] = rk

    # Always-on optimization suggestions for RK (show how to potentially reach lower RK).
    try:
        results.setdefault("suggestions", {})
        results["suggestions"]["risikoklasse"] = diagnose_optimization_suggestions_for_node(
            rk_node,
            current_data,
            output_field="risikoklasse",
            current_value=rk,
            limit=3,
        )
    except Exception:
        pass

    # Step 3: Relevant bilag (optional)
    bilag_node = nodes.get("Relevant bilag") or _find_node_by_keywords(nodes, ["relevant bilag", "bilag"])
    if bilag_node:
        bilag_res = evaluate_decision_node(bilag_node, current_data)
        if bilag_res:
            bilag_raw = bilag_res.get("relevant_bilag") if isinstance(bilag_res, dict) else None
            if bilag_raw is None:
                bilag_raw = bilag_res.get("value") if isinstance(bilag_res, dict) else None
            bilag_token = _parse_relevant_bilag_token(bilag_raw) if bilag_raw is not None else None
            results["relevant_bilag"] = {
                "value": bilag_token,
                "matched_rule_id": bilag_res.get("_matched_rule_id")
            }

            bilagsinfo = bilag_res.get("Bilagsinformation") if isinstance(bilag_res, dict) else None
            if bilagsinfo not in (None, "", [], {}):
                results["bilagsinformation"] = bilagsinfo

            bilag_titel = bilag_res.get("bilag_titel") if isinstance(bilag_res, dict) else None
            if bilag_titel not in (None, "", [], {}):
                results["bilag_titel"] = {
                    "value": bilag_titel,
                    "matched_rule_id": bilag_res.get("_matched_rule_id"),
                }
        else:
            results["debug_bilag"] = {
                "inputs_present": list(current_data.keys()),
                "anvendelseskategori": current_data.get("anvendelseskategori"),
                "risikoklasse": current_data.get("risikoklasse"),
            }
            results.setdefault("missing_inputs", [])
            results["missing_inputs"] = (results.get("missing_inputs") or []) + diagnose_missing_inputs_for_node(bilag_node, current_data)
            results.setdefault("candidates", {})
            results["candidates"]["relevant_bilag"] = diagnose_possible_outputs_for_node(
                bilag_node,
                current_data,
                output_field="relevant_bilag",
            )

    return results

def evaluate_decision_node(node, input_data, hit_policy=None):
    """Evaluerer en enkelt decision table node
    
    Args:
        node: Decision table node dict
        input_data: Input data dict
        hit_policy: Override hit policy ('first' or 'collect'). If None, uses node's hitPolicy
    
    Returns:
        For 'first' policy: Single result dict or None (includes _matched_rule_id)
        For 'collect' policy: List of all matching results
    """
    rules = node["content"]["rules"]
    inputs_map = {
        i.get("field"): i.get("id")
        for i in node["content"].get("inputs", [])
        if isinstance(i, dict) and i.get("field") and i.get("id")
    }
    outputs = node["content"].get("outputs", [])
    
    if not outputs:
        return None if hit_policy == 'first' else []
    
    # Support multiple outputs for collect policy
    outputs_map = {
        o.get("field"): o.get("id")
        for o in outputs
        if isinstance(o, dict) and o.get("field") and o.get("id")
    }
    
    # Determine hit policy
    if hit_policy is None:
        hit_policy = node["content"].get("hitPolicy", "first")
    
    matching_results = []
    
    for rule_index, rule in enumerate(rules):
        match = True
        match = True

        # VIGTIGT: Vi skal matche imod alle forventede (ikke-tomme) betingelser i reglen.
        # Hvis reglen forventer et felt (expected != "") men feltet mangler i input, skal reglen IKKE matche.
        for field, rule_id in inputs_map.items():
            expected = rule.get(rule_id, "")
            if expected == "":
                # Ingen betingelse sat for dette input
                continue

            if field not in input_data:
                # Felt kræves af reglen men mangler i input -> intet match
                match = False
                break

            value = input_data[field]

            # Konverter værdi baseret på type
            if isinstance(value, bool):
                # Understøt også multi-options og citations i expected
                if "," in expected or '"' in expected:
                    if not check_string_condition(str(value).lower(), expected.lower()):
                        match = False
                        break
                else:
                    if str(value).lower() != expected.lower():
                        match = False
                        break
            elif isinstance(value, (int, float)):
                # Håndter numeriske sammenligninger og lister
                if not check_numeric_condition(value, expected):
                    match = False
                    break
            elif isinstance(value, str):
                # Håndter string matching (inkl. quoted og lister)
                if not check_string_condition(value, expected):
                    match = False
                    break
            else:
                # Ukendt type -> fallback til strengsammenligning
                if not check_string_condition(str(value), expected):
                    match = False
                    break
        
        if match:
            # Build result with all outputs
            result = {
                "_description": rule.get("_description", ""),
                "_matched_rule_id": f"{node['id']}_rule_{rule_index}",
                "_matched_rule_index": rule_index,
                "_matched_rule_number": rule_index + 1,
                "_matched_node_id": node.get("id"),
                "_matched_node_name": node.get("name"),
            }
            
            for field, output_id in outputs_map.items():
                result_value = rule.get(output_id)
                if isinstance(result_value, str):
                    result_value = result_value.strip()
                    # Many fields in the JSON model are stored as a quoted string literal (e.g. "\"1.3.1 og 1.3.2\"").
                    # Unwrap a single pair of surrounding quotes to get clean text for the frontend.
                    if len(result_value) >= 2 and result_value.startswith('"') and result_value.endswith('"'):
                        result_value = result_value[1:-1]
                result[field] = result_value
            
            # For backwards compatibility with single output
            if len(outputs_map) == 1:
                single_field = list(outputs_map.keys())[0]
                result["value"] = result[single_field]
                result["description"] = result["_description"]
            
            if hit_policy == "first":
                return result
            else:
                matching_results.append(result)
    
    return None if hit_policy == "first" else matching_results


def diagnose_missing_inputs_for_node(node, input_data: dict, top_k_rules: int = 5):
    """Generate user-facing hints about which inputs are missing.

    This is used when a decision node returns no match. We look for "near matches":
    rules where all provided inputs satisfy their conditions, but some required fields
    are missing. Those missing fields are excellent candidates to ask the user for.

    Returns a list of dicts:
      { field, question, node_name, missing_in_rules, score }
    """
    try:
        content = (node or {}).get("content", {})
        rules = content.get("rules", []) or []
        inputs = content.get("inputs", []) or []

        field_to_question = {
            i.get("field"): (i.get("name") or i.get("field"))
            for i in inputs
            if isinstance(i, dict) and i.get("field")
        }

        inputs_map = {
            i.get("field"): i.get("id")
            for i in inputs
            if isinstance(i, dict) and i.get("field") and i.get("id")
        }

        def _is_missing_value(v):
            return v is None or (isinstance(v, str) and v.strip() == "")

        def _check_condition(value, expected: str) -> bool:
            if isinstance(value, bool):
                # Model stores bools as 'true'/'false'
                if "," in expected or '"' in expected:
                    return check_string_condition(str(value).lower(), expected.lower())
                return str(value).lower() == expected.lower()
            if isinstance(value, (int, float)):
                return check_numeric_condition(value, expected)
            if isinstance(value, str):
                return check_string_condition(value, expected)
            return check_string_condition(str(value), expected)

        # 1) Near-match candidates: mismatches == 0 and missing_fields > 0
        candidates = []
        for rule_index, rule in enumerate(rules):
            satisfied = 0
            mismatched = 0
            missing_fields = []
            required_count = 0

            for field, rule_id in inputs_map.items():
                expected = (rule.get(rule_id, "") or "").strip()
                if expected == "":
                    continue
                required_count += 1

                value = input_data.get(field)
                if field not in input_data or _is_missing_value(value):
                    missing_fields.append(field)
                    continue

                if _check_condition(value, expected):
                    satisfied += 1
                else:
                    mismatched += 1

            if required_count == 0:
                continue

            if mismatched == 0 and satisfied > 0 and missing_fields:
                candidates.append(
                    {
                        "rule_index": rule_index,
                        "rule_number": rule_index + 1,
                        "satisfied": satisfied,
                        "missing_fields": missing_fields,
                    }
                )

        # Sort candidates by: most satisfied, fewest missing
        candidates.sort(key=lambda c: (-c["satisfied"], len(c["missing_fields"])))
        candidates = candidates[: max(1, int(top_k_rules or 5))]

        field_score = {}
        field_count = {}

        for c in candidates:
            for f in c["missing_fields"]:
                field_count[f] = field_count.get(f, 0) + 1
                field_score[f] = field_score.get(f, 0) + c["satisfied"]

        # 2) Fallback: if no near-matches, suggest fields frequently used in the node.
        if not field_count:
            overall_count = {}
            for rule in rules:
                for field, rule_id in inputs_map.items():
                    expected = (rule.get(rule_id, "") or "").strip()
                    if expected != "":
                        overall_count[field] = overall_count.get(field, 0) + 1

            for f, cnt in overall_count.items():
                v = input_data.get(f)
                if f not in input_data or _is_missing_value(v):
                    field_count[f] = cnt
                    field_score[f] = cnt

        node_name = (node or {}).get("name")
        hints = []
        for f in field_count.keys():
            hints.append(
                {
                    "field": f,
                    "question": field_to_question.get(f) or f,
                    "node_name": node_name,
                    "missing_in_rules": field_count.get(f, 0),
                    "score": field_score.get(f, 0),
                }
            )

        hints.sort(key=lambda h: (-h.get("score", 0), -h.get("missing_in_rules", 0), h.get("field", "")))
        return hints
    except Exception:
        return []


def diagnose_possible_outputs_for_node(node, input_data: dict, output_field: str | None = None, limit: int = 12):
    """Suggest possible output values for a decision node given partial inputs.

    We keep any rule that has *no contradictions* with the provided inputs.
    Missing required inputs are treated as "unknown" and tracked so the UI can ask for them.

    Returns a list of candidates:
      { value, missing_fields, missing_questions, satisfied, missing_count, rule_number, node_name }
    """
    try:
        content = (node or {}).get("content", {})
        rules = content.get("rules", []) or []
        inputs = content.get("inputs", []) or []
        outputs = content.get("outputs", []) or []

        inputs_map = {
            i.get("field"): i.get("id")
            for i in inputs
            if isinstance(i, dict) and i.get("field") and i.get("id")
        }
        outputs_map = {
            o.get("field"): o.get("id")
            for o in outputs
            if isinstance(o, dict) and o.get("field") and o.get("id")
        }

        if not outputs_map:
            return []

        if output_field is None:
            # Prefer the single output if there is only one.
            if len(outputs_map) == 1:
                output_field = list(outputs_map.keys())[0]
            else:
                # Fallback: pick the first output field.
                output_field = list(outputs_map.keys())[0]

        output_id = outputs_map.get(output_field)
        if not output_id:
            return []

        field_to_question = {
            i.get("field"): (i.get("name") or i.get("field"))
            for i in inputs
            if isinstance(i, dict) and i.get("field")
        }

        def _is_missing_value(v):
            return v is None or (isinstance(v, str) and v.strip() == "")

        def _check_condition(value, expected: str) -> bool:
            if isinstance(value, bool):
                if "," in expected or '"' in expected:
                    return check_string_condition(str(value).lower(), expected.lower())
                return str(value).lower() == expected.lower()
            if isinstance(value, (int, float)):
                return check_numeric_condition(value, expected)
            if isinstance(value, str):
                return check_string_condition(value, expected)
            return check_string_condition(str(value), expected)

        candidates_by_value = {}

        for rule_index, rule in enumerate(rules):
            contradictions = 0
            satisfied = 0
            missing_fields = []

            for field, rule_id in inputs_map.items():
                expected = (rule.get(rule_id, "") or "").strip()
                if expected == "":
                    continue

                value = input_data.get(field)
                if field not in input_data or _is_missing_value(value):
                    missing_fields.append(field)
                    continue

                if _check_condition(value, expected):
                    satisfied += 1
                else:
                    contradictions += 1
                    break

            if contradictions:
                continue

            out_val = rule.get(output_id)
            if isinstance(out_val, str):
                out_val = out_val.strip()
                if len(out_val) >= 2 and out_val.startswith('"') and out_val.endswith('"'):
                    out_val = out_val[1:-1]

            if out_val in (None, ""):
                continue

            cand = {
                "value": out_val,
                "missing_fields": missing_fields,
                "missing_questions": [field_to_question.get(f) or f for f in missing_fields],
                "satisfied": satisfied,
                "missing_count": len(missing_fields),
                "rule_number": rule_index + 1,
                "node_name": (node or {}).get("name"),
            }

            # Keep the "best" rule for each output value: fewest missing, then most satisfied.
            prev = candidates_by_value.get(out_val)
            if prev is None:
                candidates_by_value[out_val] = cand
            else:
                better = (cand["missing_count"], -cand["satisfied"], cand["rule_number"]) < (prev["missing_count"], -prev["satisfied"], prev["rule_number"])
                if better:
                    candidates_by_value[out_val] = cand

        out = list(candidates_by_value.values())
        out.sort(key=lambda c: (c.get("missing_count", 0), -c.get("satisfied", 0), str(c.get("value", ""))))
        if limit is not None:
            out = out[: max(0, int(limit))]
        return out
    except Exception:
        return []

def check_numeric_condition(value, expected):
    """Tjekker numeriske betingelser som <=, >=, <, >, intervaller"""
    expected = (expected or "").strip()
    if expected.startswith("<="):
        return value <= float(expected[2:])
    elif expected.startswith(">="):
        return value >= float(expected[2:])
    elif expected.startswith("<"):
        return value < float(expected[1:])
    elif expected.startswith(">"):
        return value > float(expected[1:])
    elif "," in expected:
        # Håndter multiple værdier
        valid_values = [v.strip() for v in expected.split(",")]
        return str(value) in valid_values
    else:
        try:
            return float(value) == float(expected)
        except:
            return str(value) == expected

def check_string_condition(value, expected):
    """Tjekker string betingelser inkl. quoted strings"""
    val = (value or "").strip().lower()
    exp = (expected or "").strip().lower()
    # Some model cells contain newline-separated option lists.
    # The csv module raises on embedded newlines unless the input is handled carefully,
    # so normalize newlines/semicolons into commas before parsing.
    exp = exp.replace("\r\n", "\n").replace("\r", "\n")

    # Hvis vi har en liste (komma/linjeskift/semicolon-separeret), parse alle muligheder
    if ',' in exp or '\n' in exp or ';' in exp:
        # Brug CSV-parser for at respektere citations-tegn og undgå split på kommaer inde i citations
        # (efter vi har normaliseret linjeskift/semicolons til komma).
        import csv
        exp_list = exp.replace("\n", ",").replace(";", ",")
        try:
            tokens = next(csv.reader([exp_list], skipinitialspace=True))
        except Exception:
            # Fallback: simple split if csv parsing fails for any reason
            tokens = [t.strip() for t in exp_list.split(',')]
        options = []
        for t in tokens:
            tt = t.strip()
            if len(tt) >= 2 and tt.startswith('"') and tt.endswith('"'):
                tt = tt[1:-1]
            options.append(tt)

        # Bilag aliasing: allow e.g. "1" to match "1a" and "1.1" to match "1b".
        norm_val = _normalize_bilag_token_for_compare(val)
        if norm_val is not None:
            for opt in options:
                norm_opt = _normalize_bilag_token_for_compare(opt)
                if norm_opt is not None and norm_opt == norm_val:
                    return True
        return val in options

    # Enkelt quoted værdi
    if len(exp) >= 2 and exp.startswith('"') and exp.endswith('"'):
        unquoted = exp[1:-1]
        norm_val = _normalize_bilag_token_for_compare(val)
        norm_exp = _normalize_bilag_token_for_compare(unquoted)
        if norm_val is not None and norm_exp is not None:
            return norm_val == norm_exp
        return val == unquoted

    # Simpel streng uden citation
    norm_val = _normalize_bilag_token_for_compare(val)
    norm_exp = _normalize_bilag_token_for_compare(exp)
    if norm_val is not None and norm_exp is not None:
        return norm_val == norm_exp
    return val == exp


def _parse_expected_numeric(expected: str):
    """Parse a numeric condition string like '<=600' into (op, threshold).

    Returns (op, threshold_float) or (None, None) if not parseable.
    """
    try:
        s = (expected or "").strip()
        for op in ("<=", ">=", "<", ">"):
            if s.startswith(op):
                return op, float(s[len(op):].strip())
        # single numeric equality
        try:
            return "==", float(s)
        except Exception:
            return None, None
    except Exception:
        return None, None


def _numeric_adjustment(value, expected: str):
    """Return a dict describing how far a numeric value is from satisfying a condition.

    If the condition is satisfied or not numeric-comparable, returns None.
    Output shape:
      { field_current, op, threshold, direction, delta_abs }
    """
    try:
        op, thr = _parse_expected_numeric(expected)
        if op is None:
            return None
        v = float(value)

        ok = check_numeric_condition(v, expected)
        if ok:
            return None

        # Direction indicates which way the number must move to satisfy the constraint.
        if op in ("<=", "<"):
            return {
                "field_current": v,
                "op": op,
                "threshold": thr,
                "direction": "decrease",
                "delta_abs": max(0.0, v - thr),
            }
        if op in (">=", ">"):
            return {
                "field_current": v,
                "op": op,
                "threshold": thr,
                "direction": "increase",
                "delta_abs": max(0.0, thr - v),
            }
        if op == "==":
            return {
                "field_current": v,
                "op": op,
                "threshold": thr,
                "direction": "set",
                "delta_abs": abs(v - thr),
            }
        return None
    except Exception:
        return None


def diagnose_optimization_suggestions_for_node(
    node,
    input_data: dict,
    output_field: str,
    current_value: int | None,
    limit: int = 5,
    max_numeric_delta_abs: float | None = None,
):
    """Suggest "better" (lower) numeric outputs and what would be needed to reach them.

    This is intentionally phrased as: "Hvis byggeriet faktisk opfylder ..."
    We do NOT assume the user can/should change conceptual properties.

    Returns a list of suggestions:
      {
        target_value,
        missing_fields, missing_questions,
        required_fields: [{field, question, expected}],
        numeric_adjustments: [{field, question, expected, current, threshold, op, delta_abs}],
        score,
        node_name,
      }
    """
    try:
        if not node or not output_field:
            return []

        content = (node or {}).get("content", {})
        rules = content.get("rules", []) or []
        inputs = content.get("inputs", []) or []
        outputs = content.get("outputs", []) or []

        inputs_map = {
            i.get("field"): i.get("id")
            for i in inputs
            if isinstance(i, dict) and i.get("field") and i.get("id")
        }
        outputs_map = {
            o.get("field"): o.get("id")
            for o in outputs
            if isinstance(o, dict) and o.get("field") and o.get("id")
        }
        out_id = outputs_map.get(output_field)
        if not out_id:
            return []

        field_to_question = {
            i.get("field"): (i.get("name") or i.get("field"))
            for i in inputs
            if isinstance(i, dict) and i.get("field")
        }

        def _is_missing_value(v):
            return v is None or (isinstance(v, str) and v.strip() == "")

        suggestions_by_target = {}

        for rule_index, rule in enumerate(rules):
            out_raw = rule.get(out_id)
            out_int = _parse_first_int(out_raw) if out_raw is not None else None
            if out_int is None:
                continue
            if current_value is not None and out_int >= int(current_value):
                # Only "better" (lower) suggestions.
                continue

            missing_fields = []
            required_fields = []
            numeric_adjustments = []
            satisfied = 0

            for field, rule_id in inputs_map.items():
                expected = (rule.get(rule_id, "") or "").strip()
                if expected == "":
                    continue

                value = input_data.get(field)
                if field not in input_data or _is_missing_value(value):
                    missing_fields.append(field)
                    continue

                # Already provided: if it's satisfied, great.
                if isinstance(value, (int, float)):
                    if check_numeric_condition(value, expected):
                        satisfied += 1
                    else:
                        adj = _numeric_adjustment(value, expected)
                        if adj is not None:
                            if max_numeric_delta_abs is not None and adj.get("delta_abs") is not None:
                                if float(adj["delta_abs"]) > float(max_numeric_delta_abs):
                                    # Too large to be a useful "optimization" hint.
                                    numeric_adjustments = None
                                    break
                            numeric_adjustments.append(
                                {
                                    "field": field,
                                    "question": field_to_question.get(field) or field,
                                    "expected": expected,
                                    "current": value,
                                    "op": adj.get("op"),
                                    "threshold": adj.get("threshold"),
                                    "delta_abs": adj.get("delta_abs"),
                                }
                            )
                        else:
                            required_fields.append(
                                {
                                    "field": field,
                                    "question": field_to_question.get(field) or field,
                                    "expected": expected,
                                }
                            )
                elif isinstance(value, bool):
                    # If it mismatches, record as a requirement.
                    if check_string_condition(str(value).lower(), expected.lower()):
                        satisfied += 1
                    else:
                        required_fields.append(
                            {
                                "field": field,
                                "question": field_to_question.get(field) or field,
                                "expected": expected,
                            }
                        )
                else:
                    if check_string_condition(str(value), expected):
                        satisfied += 1
                    else:
                        required_fields.append(
                            {
                                "field": field,
                                "question": field_to_question.get(field) or field,
                                "expected": expected,
                            }
                        )

            if numeric_adjustments is None:
                continue

            missing_questions = [field_to_question.get(f) or f for f in missing_fields]

            # A simple score: fewer unknown/required changes is better.
            # numeric_adjustments count as "change" but we also prefer smaller deltas.
            delta_sum = 0.0
            for a in numeric_adjustments:
                try:
                    delta_sum += float(a.get("delta_abs") or 0.0)
                except Exception:
                    pass
            score = (
                10.0 * len(required_fields)
                + 5.0 * len(numeric_adjustments)
                + 2.0 * len(missing_fields)
                + (delta_sum / 1000.0)
                - (0.5 * satisfied)
            )

            suggestion = {
                "target_value": out_int,
                "missing_fields": missing_fields,
                "missing_questions": missing_questions,
                "required_fields": required_fields,
                "numeric_adjustments": numeric_adjustments,
                "score": score,
                "node_name": (node or {}).get("name"),
                "rule_number": rule_index + 1,
            }

            prev = suggestions_by_target.get(out_int)
            if prev is None or suggestion["score"] < prev.get("score", 1e9):
                suggestions_by_target[out_int] = suggestion

        out = list(suggestions_by_target.values())
        out.sort(key=lambda s: (s.get("score", 0.0), s.get("target_value", 999)))
        return out[: max(0, int(limit or 0))]
    except Exception:
        return []


def evaluate_from_bools(inputs: dict):
    """
    Bagudkompatibilitet - konverterer gamle boolean format til nyt system
    inputs = {
      "overnatning": bool,
      "selvhjulpen": bool,
      "kendskab_flugtveje": bool,
      "maks50personer": bool
    }
    Returnerer dict med kategori og beskrivelse
    """
    # Konverter til nyt format med defaults
    expanded_inputs = {
        "overnatning": inputs.get("overnatning", False),
        "kendskab_flugtveje": inputs.get("kendskab_flugtveje", False), 
        "selvhjulpen": inputs.get("selvhjulpen", True),
        "maks50personer": inputs.get("maks50personer", False),
        # Tilføj defaults for manglende parametre
        "antal_etager_over_terraen_BA": 1,
        "antal_etager_under_terraen_BA": 0,
        "etage_hoejde_BA": 3,
        "brandbelastning_BA": 800,
        "area_BA": 100,
        "antal_personer_BA": 25 if not inputs.get("maks50personer") else 75,
        "bygningstype": "kontorbygning",
        "fritstaaende": True,
        "direkte_udgange": True
    }
    
    # Kør gennem nyt system
    result = evaluate_complete_flow(expanded_inputs)
    
    # Returner i gamle format
    if result["success"] and result["anvendelseskategori"]:
        return {
            "kategori": result["anvendelseskategori"]["value"],
            "description": result["anvendelseskategori"]["description"]
        }
    else:
        return {"kategori": None, "description": "Ingen match fundet."}


def evaluate_krav(inputs: dict):
    """
    Evaluerer Krav.json baseret på brandklasse og relevant bilag
    
    Args:
        inputs: Dict med parametre inkl. Relevant_bilag, brandklasse, osv.
    
    Returns:
        Dict med liste af alle matchende krav
    """
    global KRAV_MODEL
    if KRAV_MODEL is None:
        try:
            KRAV_MODEL = load_krav()
        except Exception as e:
            return {
                "success": False,
                "error": f"Kunne ikke indlæse Krav.json: {str(e)}",
                "krav": []
            }
    
    # Find Designkrav decision table
    nodes = {node["name"]: node for node in KRAV_MODEL.get("nodes", []) if node.get("type") == "decisionTableNode"}
    krav_node = nodes.get("Designkrav")
    
    if not krav_node:
        return {
            "success": False,
            "error": "Kunne ikke finde 'Designkrav' node i Krav.json",
            "krav": []
        }
    
    # Evaluate with collect policy to get all matching requirements
    matching_krav = evaluate_decision_node(krav_node, inputs, hit_policy="collect")
    
    return {
        "success": True,
        "krav": matching_krav,
        "count": len(matching_krav)
    }


def generate_explanation(inputs: dict, results: dict):
    """
    Genererer en menneskelig forklaring på hvordan anvendelseskategori, 
    risikoklasse og brandklasse blev bestemt baseret på inputs og matched rules.
    
    Args:
        inputs: Brugerens oprindelige inputs
        results: Output fra evaluate_complete_flow eller evaluate_basic_flow
    
    Returns:
        Dict med strukturerede forklaringer for hvert beslutningslag
    """
    model = get_brandtree()
    nodes = {node["name"]: node for node in model.get("nodes", []) if node.get("type") == "decisionTableNode"}
    
    explanations = {
        "anvendelseskategori": None,
        "risikoklasse": None,
        "brandklasse": None,
        "summary": ""
    }
    
    # Helper function to find rule by ID
    def find_rule_in_node(node, rule_id):
        if not node or not rule_id:
            return None
        rules = node.get("content", {}).get("rules", [])
        for rule in rules:
            if rule.get("_id") == rule_id:
                return rule
        return None
    
    # Helper function to format input conditions
    def format_conditions(node, rule, inputs_data):
        conditions = []
        input_defs = node.get("content", {}).get("inputs", [])
        
        for inp in input_defs:
            field = inp.get("field")
            input_id = inp.get("id")
            name = inp.get("name", field)
            
            # Get the condition from the rule
            condition_value = rule.get(input_id, "")
            if not condition_value or condition_value == "":
                continue
            
            # Get the actual input value
            actual_value = inputs_data.get(field)
            
            # Format the condition nicely
            if condition_value == "true":
                conditions.append(f"{name}: Ja")
            elif condition_value == "false":
                conditions.append(f"{name}: Nej")
            elif actual_value is not None:
                conditions.append(f"{name}: {actual_value}")
            else:
                conditions.append(f"{name}: {condition_value}")
        
        return conditions
    
    # Explain Anvendelseskategori
    if results.get("anvendelseskategori"):
        ak_result = results["anvendelseskategori"]
        ak_node = nodes.get("Anvendelseskategori 2.0") or _find_node_by_keywords(nodes, ["anvendelseskategori"])
        
        if ak_node and ak_result.get("matched_rule_id"):
            rule = find_rule_in_node(ak_node, ak_result["matched_rule_id"])
            if rule:
                conditions = format_conditions(ak_node, rule, inputs)
                explanations["anvendelseskategori"] = {
                    "value": ak_result["value"],
                    "description": rule.get("_description", ak_result.get("description", "")),
                    "conditions": conditions,
                    "text": f"Dit byggeri er klassificeret som Anvendelseskategori {ak_result['value']}. " +
                           f"{rule.get('_description', '')} " +
                           f"Dette blev bestemt baseret på: {', '.join(conditions) if conditions else 'de angivne parametre'}."
                }
    
    # Explain Risikoklasse
    if results.get("risikoklasse"):
        rk_result = results["risikoklasse"]
        rk_node = nodes.get("Risikoklasse") or _find_node_by_keywords(nodes, ["risikoklasse"])
        
        if rk_node and rk_result.get("matched_rule_id"):
            rule = find_rule_in_node(rk_node, rk_result["matched_rule_id"])
            if rule:
                conditions = format_conditions(rk_node, rule, inputs)
                explanations["risikoklasse"] = {
                    "value": rk_result["value"],
                    "description": rule.get("_description", rk_result.get("description", "")),
                    "conditions": conditions,
                    "text": f"Risikoklasse {rk_result['value']} blev tildelt. " +
                           f"{rule.get('_description', '')} " +
                           f"Dette baseres på: anvendelseskategori {results.get('anvendelseskategori', {}).get('value')}, " +
                           f"samt {', '.join(conditions) if conditions else 'bygningens karakteristika'}."
                }
    
    # Explain Brandklasse
    if results.get("brandklasse"):
        bk_result = results["brandklasse"]
        bk_node = nodes.get("Præ-accepterede løsninger")
        
        if bk_node and bk_result.get("matched_rule_id"):
            rule = find_rule_in_node(bk_node, bk_result["matched_rule_id"])
            if rule:
                conditions = format_conditions(bk_node, rule, inputs)
                explanations["brandklasse"] = {
                    "value": bk_result.get("value"),
                    "description": rule.get("_description", bk_result.get("description", "")),
                    "conditions": conditions,
                    "text": f"Brandklasse {bk_result.get('value')} er gældende. " +
                           f"{rule.get('_description', '')} " +
                           f"Klassificeringen tager udgangspunkt i: {', '.join(conditions) if conditions else 'byggeriets egenskaber og relevant bilag'}."
                }
    
    # Generate summary
    summary_parts = []
    if explanations["anvendelseskategori"]:
        summary_parts.append(explanations["anvendelseskategori"]["text"])
    if explanations["risikoklasse"]:
        summary_parts.append(explanations["risikoklasse"]["text"])
    if explanations["brandklasse"]:
        summary_parts.append(explanations["brandklasse"]["text"])
    
    explanations["summary"] = " ".join(summary_parts)
    
    return explanations
