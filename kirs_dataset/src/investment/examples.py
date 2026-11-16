import json

from .common import stable_id


def examples_from_facts(reports, facts):
    """Deterministic grounded examples, explicitly not unreviewed human gold."""
    examples = []
    for r in reports:
        candidates = [f for f in facts if f["report_id"] == r["report_id"]
                      and f["extraction_status"] == "dual_parser_agreed" and f["value"] is not None]
        latest = max(f["fiscal_year"] for f in candidates)
        selected = [f for f in candidates if f["fiscal_year"] == latest and f["metric"] in {"revenue", "operating_profit", "per"}]
        for f in selected:
            context = {"source_id": r["source_id"], "report_id": r["report_id"], "family_id": r["family_id"],
                       "source_url": r["source_url"], "evidence_page": f["page"], "evidence_table": f["table"],
                       "evidence_row": f["row_label"], "evidence_column": f["column_label"], "evidence_bbox": f["bbox"],
                       "fact_id": f["fact_id"], "as_of": r["available_at"], "target_period": f["fiscal_period"],
                       "label_status": "rule_verified_not_human_gold", "training_use_permitted": False,
                       "evidence_context": {k: f[k] for k in ["row_label", "column_label", "raw_value", "unit", "currency", "fiscal_period", "value_type", "estimate_owner", "statement_scope"]},
                       "split_group": r["family_id"], "generation_method": "deterministic_template_no_llm"}
            owner = "작성기관 전망" if f["value_type"] == "forecast" else "보고서 기재 실적"
            answer = f"{f['raw_value']} {f['unit']} ({owner}; OpenDART 미대조)."
            examples.append({"example_id": stable_id(f["fact_id"], "qa"), "task": "grounded_qa",
                "question": f"{r['publication_date']} 발간 {r['company_name']} 보고서의 {latest}년 {f['metric']} 값은?",
                "answer": answer, **context})
        if selected:
            f = selected[0]
            examples.append({"example_id": stable_id(r["report_id"], "extract"), "task": "structured_extraction",
                "instruction": "지정한 원문 표의 값·단위·시점·전망 주체를 분리해 추출하라.",
                "input": {"page": f["page"], "table": f["table"], "row": f["row_label"], "column": f["column_label"],
                          **{k: f[k] for k in ["raw_value", "unit", "currency", "value_type", "estimate_owner", "statement_scope"]}},
                "output": {k: f[k] for k in ["metric", "value", "unit", "currency", "fiscal_period", "value_type", "estimate_owner", "statement_scope"]},
                "source_id": r["source_id"], "report_id": r["report_id"], "family_id": r["family_id"],
                "source_url": r["source_url"], "evidence_page": f["page"], "fact_id": f["fact_id"],
                "as_of": r["available_at"], "target_period": f["fiscal_period"], "split_group": r["family_id"],
                "label_status": "rule_verified_not_human_gold", "training_use_permitted": False,
                "generation_method": "deterministic_template_no_llm"})
        # Missing public timestamp is an actual evidence gap, NOT a made-up claim
        # that no target price exists in an unread part of a report.
        examples.append({"example_id": stable_id(r["report_id"], "unknown"), "task": "unanswerable",
            "question": f"이 {r['company_name']} 보고서가 인터넷에 최초 공개된 정확한 시각은?",
            "answer": "확인 불가. 발간일만 확인되며 실제 최초 공개 시각은 검증되지 않았다. 수집 시각을 공개 시각으로 대체할 수 없다.",
            "source_id": r["source_id"], "report_id": r["report_id"], "family_id": r["family_id"],
            "source_url": r["source_url"], "evidence_page": 1, "evidence_scope": "PDF cover date and source metadata",
            "evidence_context": {"publication_date": r["publication_date"], "published_at": None, "public_time_verification": "date_only_unverified_exact_time"},
            "as_of": r["available_at"], "target_period": r["publication_date"], "split_group": r["family_id"],
            "label_status": "metadata_gap_verified_not_human_gold", "training_use_permitted": False,
            "generation_method": "deterministic_template_no_llm"})
    return examples


def to_chat_examples(examples, *, rights_confirmed=False, human_reviewed=False):
    if not rights_confirmed or not human_reviewed:
        raise PermissionError("Training export requires rights clearance and reviewed labels")
    for example in examples:
        if example["task"] not in {"grounded_qa", "unanswerable"}:
            continue
        yield {"messages": [{"role": "system", "content": "출처에 근거해 답하고 근거가 없으면 확인 불가라고 답하라."},
                            {"role": "user", "content": "근거 데이터: " + json.dumps(example["evidence_context"], ensure_ascii=False) + "\n질문: " + example["question"]},
                            {"role": "assistant", "content": example["answer"]}],
               "metadata": {"source_id": example["source_id"], "split_group": example["split_group"]}}
