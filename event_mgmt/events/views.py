from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Event, Ticket, Attendee
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django import forms
from .models import Event
from django.contrib.auth import update_session_auth_hash
from .forms import ProfileEditForm, CustomPasswordChangeForm
from django.http import JsonResponse
from django.urls import reverse
from django.db import transaction
from .utils import send_notification_email
import requests
from django.conf import settings
import uuid

# Get the custom User model
User = get_user_model()

# Custom Signup Form (Fixes the Manager Error)
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User  # Use the custom user model
        fields = ["username", "email", "password1", "password2"]

# Update Signup View to Use Custom Form
def signup_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("event_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomUserCreationForm()
    return render(request, "events/signup.html", {"form": form})

# User Login
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("event_list")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, "events/login.html", {"form": form})

# User Logout
@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


# Event form
class EventForm(forms.ModelForm):
    date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
        input_formats=["%Y-%m-%dT%H:%M"]
    )

    class Meta:
        model = Event
        fields = ["name", "description", "date", "location", "is_ticketed", "price"]

# Event List
class EventListView(ListView):
    model = Event
    template_name = "events/event_list.html"
    context_object_name = "events"

# Event Detail
class EventDetailView(DetailView):
    model = Event
    template_name = "events/event_detail.html"

# Create Event (Only for Logged-in Users)
class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm  # Use our custom form
    template_name = "events/event_form.html"

    def form_valid(self, form):
        form.instance.creator = self.request.user
        return super().form_valid(form)

# Update Event (Only for Creator)
class EventUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = "events/event_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)

        # Notify all attendees about the update
        attendees = Attendee.objects.filter(event=self.object)
        for attendee in attendees:
            send_notification_email(
                subject="Event Update Notification",
                message=f"Hello {attendee.user.username},\n\nThe event '{self.object.name}' has been updated. Check the event page for details.",
                recipient_email=attendee.user.email
            )

        return response

    def test_func(self):
        return self.get_object().creator == self.request.user

# Delete Event (Only for Creator)
class EventDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Event
    success_url = reverse_lazy("event_list")
    template_name = "events/event_confirm_delete.html"

    def test_func(self):
        event = self.get_object()
        return event.creator == self.request.user


@login_required
def event_list(request):
    # Get all events
    events = Event.objects.all()

    # Directly query if the current user is attending or has created an event
    user_attended_events = Event.objects.filter(attendee__user=request.user)
    user_created_events = Event.objects.filter(creator=request.user)

    # Render the template with the updated context
    return render(request, "events/event_list.html", {
        "events": events,
        "user_attended_events": user_attended_events,
        "user_created_events": user_created_events
    })

@login_required
def my_events(request):
    # Get the events the user has created
    created_events = Event.objects.filter(creator=request.user)

    # Get the events the user has joined (from the Attendee model)
    joined_events = Event.objects.filter(attendee__user=request.user)

    # Render both sets of events on the same page
    return render(request, "events/my_events.html", {
        "created_events": created_events,
        "joined_events": joined_events
    })

@login_required
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # Check if the user has bought a ticket for the event
    has_ticket = Ticket.objects.filter(event=event, buyer=request.user).exists()

    # Prefetch attendees to handle large attendee sets efficiently
    attendees = Attendee.objects.filter(event=event)
    is_attendee = attendees.filter(user=request.user).exists()

    context = {
        'event': event,
        'is_attendee': is_attendee,
        'attendees': attendees,  # This can be used for pagination or display of attendees
        'has_ticket': has_ticket,  # Pass the ticket information to the template
    }

    return render(request, 'events/event_detail.html', context)


@login_required
def join_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # Check if the user has already joined the event
    if Attendee.objects.filter(event=event, user=request.user).exists():
        messages.warning(request, "You have already joined this event!")
    else:
        # Add user as an attendee for the event
        Attendee.objects.create(event=event, user=request.user)
        messages.success(request, f"You have successfully joined the event: {event.name}!")
        try:
            # Send email notification to the user
            send_notification_email(
                subject="Event Registration Confirmed!",
                message=f"Hello {request.user.username},\n\nYou have successfully joined the event: {event.name}.",
                recipient_email=request.user.email
                )
        except Exception as e:
            messages.warning(request, "Email sending failed due to poor network")
            print(e)


    # After joining, redirect to the event_list page to reflect the updated status
    return redirect("event_list")

@login_required
def unjoin_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    try:
        # Find the attendee record and delete it
        attendee = Attendee.objects.get(event=event, user=request.user)
        attendee.delete()

        if event.is_ticketed:
            ticket = Ticket.objects.filter(event=event, buyer=request.user).first()
            ticket.delete()
            messages.success(request, "Your ticket has been refunded!")
        else:
            print("no ticket")
        messages.success(request, "You have left the event!")
        try:
            # Send email notification to the user
            send_notification_email(
            subject="Event Unjoined",
            message=f"Hello {request.user.username},\n\nYou have left the event: {event.name}.",
            recipient_email=request.user.email
        )
        except Exception as e:
            messages.warning(request, "Email sending failed due to poor network")
            print(e)

    except Attendee.DoesNotExist:
        messages.warning(request, "You are not part of this event!")

    # After leaving, redirect to the event_list page
    return redirect("event_list")


@login_required
def mock_paystack_redirect(request, reference):
    messages.info(request, "[MOCK] Payment redirect triggered.")
    return redirect(f"{reverse('verify_payment')}?reference={reference}")


@login_required
def buy_ticket(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # Check if user already has a ticket
    if Ticket.objects.filter(event=event, buyer=request.user).exists():
        messages.warning(request, "You already have a ticket for this event!")
        return redirect("event_detail", event_id=event_id)

    # Create a ticket entry before payment
    #ticket = Ticket.objects.create(event=event, buyer=request.user)
    #messages.success(request, "Ticket created. Proceeding to payment...")

    try:

        # Initiate payment (real or mock)
        payment_url, reference = initiate_paystack_payment(
            user=request.user,
            amount=event.price,
            email=request.user.email,
            event_id=event.id  # Pass event ID explicitly
                )

        if settings.USE_MOCK_PAYSTACK:
            # Save mock session data as strings for JSON-safe handling
            request.session["mock_event_id"] = str(event.id)
            request.session["mock_reference"] = reference

        if payment_url:
            return redirect(payment_url)
    except Exception as e:
        ticket.delete()


        messages.error(request, "Payment initiation failed. Please try again.")
    return redirect("event_detail", event_id=event_id)



@login_required
def verify_payment(request):
    reference = request.GET.get("reference")
    if not reference:
        messages.error(request, "Invalid payment reference.")
        return redirect("event_list")

    # Attempt real Paystack verification
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        res_data = response.json()

        if res_data.get("status") and res_data["data"]["status"] == "success":
            event_id_str = res_data["data"]["metadata"].get("event_id")
            if not event_id_str:
                messages.error(request, "Payment verification failed: Event info missing.")
                return redirect("event_list")

            event = get_object_or_404(Event, id=uuid.UUID(event_id_str))
            Ticket.objects.get_or_create(event=event, buyer=request.user)
            Attendee.objects.get_or_create(event=event, user=request.user)
            messages.success(request, "Payment successful! You have been registered for the event.")

            return redirect("event_detail", event_id=event.id)

        else:
            print("⚠️ Real Paystack verification failed:", res_data)
    except requests.exceptions.RequestException as e:
        print("⚠️ Exception during real Paystack verification:", e)

    # Fallback to mock verification if real API fails
    event_id_str = request.session.get("mock_event_id")
    if not event_id_str:
        messages.error(request, "Payment verification failed. No fallback info found.")
        return redirect("event_list")

    event = get_object_or_404(Event, id=uuid.UUID(event_id_str))
    Ticket.objects.get_or_create(event=event, buyer=request.user)
    Attendee.objects.get_or_create(event=event, user=request.user)
    messages.success(request, "[MOCK] Payment successful! You have been registered for the event.")
    return redirect("event_detail", event_id=event.id)



def initiate_paystack_payment(user, amount, email, event_id):
    """
    Attempts to initiate a real Paystack payment first.
    If it fails (network, API error), fall back to mock.
    """
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "email": email,
        "amount": int(amount * 100),  # Convert to kobo
        "callback_url": settings.SITE_URL + reverse("verify_payment"),
        "metadata": {
            "event_id": str(event_id),
        },
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        response_data = response.json()

        if response.status_code == 200 and response_data.get("status"):
            # Real Paystack payment initialization successful
            return response_data["data"]["authorization_url"], response_data["data"]["reference"]
        else:
            print("⚠️ Real Paystack API call failed. Response data:", response_data)
    except requests.exceptions.RequestException as e:
        print("⚠️ Exception during real Paystack API call:", e)

    # Fall back to mock payment if real API fails
    reference = str(uuid.uuid4())
    url = reverse("mock_paystack_redirect", args=[reference])
    return url, reference


# Update Profile
@login_required
def edit_profile(request):
    if request.method == "POST":
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('event_list')  # Redirect after saving
    else:
        form = ProfileEditForm(instance=request.user)

    return render(request, 'events/edit_profile.html', {'form': form})

@login_required
def change_password(request):
    if request.method == "POST":
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, request.user)  # Keep the user logged in
            messages.success(request, "Your password was successfully updated!")
            return redirect("edit_profile")  # Redirect after successful password change
    else:
        form = CustomPasswordChangeForm(user=request.user)  # Ensure the form is created

    return render(request, "events/change_password.html", {"form": form})

