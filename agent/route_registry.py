"""
Route Registry for Kepler Tech Conversational AI.
Maps RouteName values to their handler functions.
"""

from domain.conversation_types import RouteName
from routes import (
    social_route,
    qualification_route,
    product_route,
    comparison_route,
    consumables_route,
    support_route,
    business_info_route,
)

# Route name → handler module mapping
ROUTE_HANDLERS = {
    RouteName.SOCIAL: social_route,
    RouteName.QUALIFICATION: qualification_route,
    RouteName.PRODUCT: product_route,
    RouteName.COMPARISON: comparison_route,
    RouteName.CONSUMABLES: consumables_route,
    RouteName.SUPPORT: support_route,
    RouteName.BUSINESS_INFO: business_info_route,
}


def get_handler(route_name: RouteName):
    """Returns the handler module for the given route name, or None."""
    return ROUTE_HANDLERS.get(route_name)
