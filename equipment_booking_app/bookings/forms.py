from django import forms
from django.core.exceptions import ValidationError
from .models import Booking, Profile, Equipment, Message, Notice
from django.utils import timezone
from django.contrib.auth.models import User

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['user', 'equipment', 'start_time', 'end_time', 'reason', 'project_number', 'use_location']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'reason': forms.Textarea(attrs={'placeholder': 'Type your booking justification here...'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the current logged-in user
        super(BookingForm, self).__init__(*args, **kwargs)

        # Allow superusers to select from all users, regular users can only book for themselves
        if user and user.is_superuser:
            self.fields['user'].queryset = User.objects.all()
        else:
            # Regular users can only see their own name
            self.fields['user'].queryset = User.objects.filter(id=user.id)
            self.fields['user'].initial = user  # Auto-fill with the logged-in user
            self.fields['user'].widget.attrs['readonly'] = True
            self.fields['user'].disabled = True 
            self.fields['user'].required = False  # Exclude from POST validation

    def save(self, commit=True):
        booking = super().save(commit=False)
        if commit:
            booking.save()  # Save the booking
        return booking



class ProfileForm(forms.ModelForm):
    email = forms.EmailField(required=False) 

    class Meta:
        model = Profile
        fields = ['phone_number', 'work_address', 'work_division', 'job_role', 'email']  

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply form-control class for Bootstrap styling
        self.fields['phone_number'].widget.attrs.update({'class': 'form-control'})
        self.fields['work_address'].widget.attrs.update({'class': 'form-control'})
        self.fields['work_division'].widget.attrs.update({'class': 'form-control'})
        self.fields['job_role'].widget.attrs.update({'class': 'form-control'})
        if 'instance' in kwargs:
            self.fields['email'].initial = kwargs['instance'].user.email  

    def save(self, commit=True):
        profile = super(ProfileForm, self).save(commit=False)
        user = profile.user
        user.email = self.cleaned_data['email']  # Save email to the user model
        if commit:
            user.save()
            profile.save()
        return profile


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['subject', 'content']  
        widgets = {
            'subject': forms.TextInput(attrs={'placeholder': 'Enter subject here...'}),
            'content': forms.Textarea(attrs={'placeholder': 'Type your message here...'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()  # Save the message
        return instance


class ResponseForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['response', 'read']  # Assuming 'read' indicates if the message has been responded to


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ['message'] 
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),  # Set the textarea to have 5 rows
        }
