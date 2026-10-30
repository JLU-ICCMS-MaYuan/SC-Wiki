"""单点Tc—μ*的科学对应核验；原文定位不代替对应关系。"""
from decimal import Decimal,InvalidOperation

PROMPT = """
For every item with expected_point, return point_binding:
{"verdict":"match|conflict|unknown","source_pair":{"mu_star":number,"tc_k":number}}.
Read the SOURCE pair for the CURRENT mu_star and method/pressure. Do not copy expected_point as proof.
For a sentence containing several values with "respectively", keep their actual correspondence.
Example: source reports 235 K at mu*=0.1 and 220 K at mu*=0.13.
For expected_point={mu_star:0.13,tc_k:235}, source_pair MUST be {mu_star:0.13,tc_k:220},
verdict MUST be conflict and status must not be supported. A number occurring in a range is not proof of the point.
Use unknown if the source cannot establish a unique point. Include normal valid source evidences as well.
"""

def number(value):
    if isinstance(value,bool) or value is None:return None
    try:
        value=Decimal(str(value))
        return value if value.is_finite() else None
    except (InvalidOperation,ValueError):return None

def expected_point(record):
    context=(record.get('claim') or {}).get('context') or {}
    if record.get('record_field')=='value_number':
        mu,tc=context.get('paired_mu_star'),record.get('current_value')
    elif record.get('record_field')=='payload.parameters.mu_star':
        mu,tc=record.get('current_value'),context.get('paired_tc')
    else:return None
    if isinstance(mu,dict):mu=mu.get('value_number')
    if number(mu) is None or number(tc) is None:return None
    return {'mu_star':mu,'tc_k':tc}

def verify(record,raw,result):
    expected=expected_point(record)
    if expected is None:return result
    binding=raw.get('point_binding')
    if not isinstance(binding,dict):
        if result.get('status')=='supported':
            result.update(status='unchecked',pending_review=True,review_error='point_binding_missing',
                reason='模型未返回当前Tc与μ*的完整配对核验，不能仅凭数值定位通过。')
        return result
    source=binding.get('source_pair') or {}
    valid=isinstance(source,dict) and all(number(source.get(k)) is not None for k in expected)
    same=valid and all(number(source[k])==number(expected[k]) for k in expected)
    verdict=binding.get('verdict')
    result['point_binding']={'contract':'tc-point-binding-v1','expected_point':expected,
        'source_pair':source if valid else None,'verdict':verdict}
    if verdict=='conflict' or valid and not same:
        result.update(status='unsupported',pending_review=False,
            reason='原文中的Tc与μ*对应关系不支持当前结果点。'+str(result.get('reason') or ''))
    elif result.get('status')=='supported' and not (same and verdict=='match' and result.get('evidences')):
        result.update(status='uncertain',pending_review=True,reason='当前Tc与μ*的完整配对依据不足。')
    return result
