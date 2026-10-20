"""已撤销的VASP-PBE到QE推断入口；旧记录可读，旧调用不再补值。"""
RULE = "vasp_pbe_to_qe_v1"
FUNCTIONAL = "exchange_correlation_functional"


def functional_inference_targets(settings, targets):
    return set()


def functional_inference_candidates(requests, settings, targets, context):
    return [], [{"target": item.get("target"), "reason": "functional_inference_retired"}
                for item in requests if isinstance(item, dict)] if isinstance(requests, list) else []
