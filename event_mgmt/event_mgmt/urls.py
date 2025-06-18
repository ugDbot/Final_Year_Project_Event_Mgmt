from django.urls import path
from events.views import (
    signup_view, login_view, logout_view,
    EventListView, EventDetailView, EventCreateView,
    EventUpdateView, EventDeleteView, join_event, buy_ticket, edit_profile, change_password, my_events,
    unjoin_event, event_detail, verify_payment, mock_paystack_redirect
)

urlpatterns = [
    # Authentication Routes
    path("signup/", signup_view, name="signup"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),

    # Event Routes
    path("", EventListView.as_view(), name="event_list"),
    path("event/<uuid:pk>/", EventDetailView.as_view(), name="event_detail"),
    path("event/new/", EventCreateView.as_view(), name="event_create"),
    path("event/<uuid:pk>/edit/", EventUpdateView.as_view(), name="event_edit"),
    path("event/<uuid:pk>/delete/", EventDeleteView.as_view(), name="event_delete"),

    # User Event Management
    path("event/<uuid:event_id>/join/", join_event, name="join_event"),
    path("my-events/", my_events, name="my_events"),
    path("event/<uuid:event_id>/unjoin/", unjoin_event, name="unjoin_event"),
    path("event/<uuid:event_id>/", event_detail, name="event_detail"),

    # Profile Management
    path("edit-profile/", edit_profile, name="edit_profile"),
    path("change-password/", change_password, name="change_password"),

    # Paystack Payment Routes
    path('event/<uuid:event_id>/buy-ticket/', buy_ticket, name='buy_ticket'),
    path("verify-payment/", verify_payment, name="verify_payment"),
    path("mock/paystack/redirect/<str:reference>/", mock_paystack_redirect, name="mock_paystack_redirect"),


]
