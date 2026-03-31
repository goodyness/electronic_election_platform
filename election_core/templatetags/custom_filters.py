from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplies the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value

@register.filter(name='jsonify')
def jsonify(object):
    import json
    from django.utils.safestring import mark_safe
    return mark_safe(json.dumps(object))
