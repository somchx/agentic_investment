"""Versioned, deterministic expectation mapping. No LLM interpretation."""
from math import isfinite

PRESETS = {
    'revenue_non_decreasing': ('Revenue', '>=', 'value_comparison', '', False, 'Revenue current >= same period prior year'),
    'revenue_increasing': ('Revenue', '>', 'value_comparison', '', False, 'Revenue current > same period prior year'),
    'margin_non_decreasing': ('OperatingIncome', '>=', 'margin_comparison', 'Revenue', False, 'Operating margin current >= same period prior year'),
    'operating_profit_positive': ('OperatingIncome', '>', 'positive_level', '', False, 'Operating income > 0 USD'),
    'debt_non_increasing': ('LongTermDebt', '<=', 'value_comparison', '', True, 'Noncurrent long-term debt current <= same period prior year'),
}

def normalize_rule(definition, metric, comparison, threshold, kind, denominator='', instant=False):
    if definition is None:
        if threshold is None or not isfinite(threshold):
            raise ValueError('Numeric rules require a finite threshold')
        return metric, comparison, threshold, kind, denominator, instant, None
    if not isinstance(definition, dict) or definition.get('version') != 1:
        raise ValueError('Unsupported rule definition version')
    period = definition.get('evaluation_period')
    if period not in ('quarterly', 'annual'):
        raise ValueError('evaluation_period must be quarterly or annual')
    preset = definition.get('preset')
    if preset in PRESETS:
        metric, comparison, mode, denominator, instant, preview = PRESETS[preset]
        threshold = 0.0 if mode == 'positive_level' else None
        kind = 'margin_level' if mode == 'margin_comparison' else 'yoy_growth'
    elif preset == 'custom':
        if kind not in ('yoy_growth', 'margin_level') or comparison not in ('>', '>=', '<', '<='):
            raise ValueError('Invalid numeric formula or operator')
        if not metric or (kind == 'margin_level' and not denominator):
            raise ValueError('Metric and ratio denominator are required')
        if threshold is None or not isfinite(threshold):
            raise ValueError('Numeric rules require a finite threshold')
        mode = kind
        preview = f'{metric}' + (f' / {denominator}' if kind == 'margin_level' else ' YoY') + f' {comparison} {threshold * 100:g}%'
    else:
        raise ValueError('Unknown expectation preset')
    rule = dict(version=1, preset=preset, mode=mode, evaluation_period=period,
                comparison_period='none' if mode in ('positive_level', 'margin_level') else 'same_period_prior_year',
                metric=metric, denominator_metric=denominator, operator=comparison, threshold=threshold,
                unit='USD' if mode in ('value_comparison', 'positive_level') else 'ratio',
                metric_definition='noncurrent_debt_excluding_current_portion_and_leases' if metric == 'LongTermDebt' else 'consolidated_USD',
                preview=preview, missing_policy='NOT_EVALUATED', temporal_policy='filed_date_as_of')
    return metric, comparison, threshold, kind, denominator, instant, rule
