from django import forms
from django.core.exceptions import ValidationError
from .models import Booking, Profile, Equipment, Message, Notice, Workflow, WorkflowStep
from django.utils import timezone
from django.contrib.auth.models import User

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['user', 'equipment', 'start_time', 'end_time', 'reason', 'project_number', 'use_location']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'reason': forms.Textarea(
                attrs={'placeholder': 'Please type the reason here...'}
            ),
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

        # Apply Bootstrap form-control class to all fields for consistent styling
        for field in self.fields.values():
            existing_classes = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (
                existing_classes + ' form-control'
            ).strip()

    def save(self, commit=True):
        booking = super().save(commit=False)
        if commit:
            booking.save()  # Save the booking
        return booking



class ProfileForm(forms.ModelForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = Profile
        fields = ['initials', 'phone_number', 'work_address', 'work_division', 'job_role', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply form-control class for Bootstrap styling
        self.fields['initials'].widget.attrs.update({'class': 'form-control'})
        self.fields['phone_number'].widget.attrs.update({'class': 'form-control'})
        self.fields['work_address'].widget.attrs.update({'class': 'form-control'})
        self.fields['work_division'].widget.attrs.update({'class': 'form-control'})
        self.fields['job_role'].widget.attrs.update({'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})
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
    workflow = forms.ModelChoiceField(
        queryset=Workflow.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control w-100"}),
    )

    class Meta:
        model = Message
        fields = ["subject", "content", "workflow"]
        widgets = {
            "subject": forms.TextInput(
                attrs={"placeholder": "Enter subject here...", "class": "form-control w-100"}
            ),
            "content": forms.Textarea(
                attrs={"placeholder": "Type your message here...", "class": "form-control w-100"}
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['workflow'].queryset = Workflow.objects.filter(created_by=user)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
        return instance


class ResponseForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['response']
        widgets = {
            'response': forms.Textarea(attrs={'placeholder': 'Type your response here...'})
        }


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ['message'] 
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),  # Set the textarea to have 5 rows
        }


class WorkflowForm(forms.ModelForm):
    qa_video_review = forms.BooleanField(
        label="Enable Manual QA Review for Each Video",
        required=False,
    )
    use_date_suffix = forms.BooleanField(
        label="Use date instead of version number in final filename?",
        required=False,
    )
    class Meta:
        model = Workflow
        fields = ['name', 'description', 'qa_video_review', 'use_date_suffix']


class WorkflowStepForm(forms.ModelForm):
    class Meta:
        model = WorkflowStep
        fields = ['action', 'order']


WorkflowStepFormSet = forms.modelformset_factory(
    WorkflowStep,
    form=WorkflowStepForm,
    extra=0,
    can_delete=True
)


class RunWorkflowForm(forms.Form):
    """Collect top level inputs for running a workflow."""

    workflow = forms.ModelChoiceField(queryset=Workflow.objects.none())
    input_path = forms.CharField(label="Input Folder", max_length=255)
    use_input_path = forms.TypedChoiceField(
        label="Is your output the same as your input folder?",
        choices=((True, "Yes"), (False, "No")),
        coerce=lambda x: x == "True",
        widget=forms.RadioSelect,
        initial=True,
    )
    output_path = forms.CharField(label="Output Folder", max_length=255, required=False)
    project_code = forms.CharField(label="Project Code", max_length=100, required=False)
    initials = forms.CharField(label="Initials", max_length=20, required=False)
    pause_between_steps = forms.BooleanField(
        label="Pause after each step for manual QA before continuing",
        required=False,
        initial=False,
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        wf_qs = kwargs.pop("workflow_queryset", None)
        super().__init__(*args, **kwargs)

        if wf_qs is not None:
            self.fields["workflow"].queryset = wf_qs
        elif self.user:
            self.fields["workflow"].queryset = Workflow.objects.filter(created_by=self.user)

        if self.user:
            profile = Profile.objects.filter(user=self.user).first()
            if profile and profile.initials:
                self.fields["initials"].initial = profile.initials
                self.fields["initials"].widget.attrs["readonly"] = True
                existing = self.fields["initials"].widget.attrs.get("class", "")
                self.fields["initials"].widget.attrs["class"] = (
                    existing + " form-control"
                ).strip()

    def clean_initials(self):
        if self.user:
            profile = Profile.objects.filter(user=self.user).first()
            if profile and profile.initials:
                return profile.initials
        return self.cleaned_data.get("initials", "")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("use_input_path"):
            cleaned["output_path"] = cleaned["input_path"]
        elif not cleaned.get("output_path"):
            raise ValidationError("Output folder required when not saving to input folder")
        return cleaned


class StepSettingsForm(forms.Form):
    """Dynamic form for per-step configuration."""

    action = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, action=None, **kwargs):
        initial = kwargs.setdefault("initial", {})
        if action:
            initial.setdefault("action", action)
        else:
            action = initial.get("action")

        super().__init__(*args, **kwargs)

        self.action = action
        if action == "trim":
            self.fields["start_seconds"] = forms.IntegerField(
                label="Seconds from Start",
                required=False,
                initial=0,
                help_text="Select how many seconds to trim from start/end",
            )
            self.fields["end_seconds"] = forms.IntegerField(
                label="Seconds from End",
                required=False,
                initial=0,
                help_text="Select how many seconds to trim from start/end",
            )
        elif action == "rename":
            self.fields["rename_pattern"] = forms.CharField(
                label="Rename Pattern",
                required=False,
                help_text="Enable smart renaming using file path and timestamp",
            )
        elif action == "convert_360_video":
            self.fields["convert_format"] = forms.ChoiceField(
                label="Convert To",
                choices=[("", "Leave unchanged"), ("mp4", "MP4"), ("avi", "AVI")],
                required=False,
            )
        elif action == "organize_files":
            self.fields["target_folder"] = forms.CharField(
                label="Target Folder",
                required=False,
            )
        elif action == "setup_structure":
            self.fields["raw_data_folder"] = forms.CharField(
                label="Raw Data Folder",
                required=True,
                widget=forms.HiddenInput(),
            )
            self.fields["full_structure"] = forms.BooleanField(
                label="Generate Full Structure",
                required=False,
                initial=False,
            )

    def clean(self):
        cleaned = super().clean()
        if self.action == "trim":
            start = cleaned.get("start_seconds") or 0
            end = cleaned.get("end_seconds") or 0
            if start < 0:
                self.add_error("start_seconds", "Must be positive")
            if end < 0:
                self.add_error("end_seconds", "Must be positive")
        return cleaned


StepSettingsFormSet = forms.formset_factory(StepSettingsForm, extra=0)



class RenameToolForm(forms.Form):
    raw_data_folder = forms.CharField(label="RAW Data Folder", max_length=255)
    output_folder = forms.CharField(label="Output Folder", max_length=255)
    user_initials = forms.CharField(label="Your Initials", max_length=10)
    full_name = forms.CharField(label="Full Name", max_length=100)
    rename_pattern = forms.CharField(label="Rename Pattern", required=False)


class ConvertToolForm(forms.Form):
    input_path = forms.CharField(label="Input Folder", max_length=255)
    format = forms.ChoiceField(label="Format", choices=[("mp4", "MP4"), ("avi", "AVI")])


class ZipToolForm(forms.Form):
    input_path = forms.CharField(label="Input Folder", max_length=255)
    output_zip = forms.CharField(label="Output Zip", max_length=255)


class VideoReviewForm(forms.Form):
    zone_id = forms.CharField(label="Zone ID", max_length=50)
    flag_manual_edit = forms.BooleanField(
        label="Flag for Manual Edit", required=False
    )


class VideoOrderForm(forms.Form):
    file_name = forms.CharField(widget=forms.HiddenInput())
    zone_id = forms.CharField(
        label="Zone ID",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "e.g. 101-A"}),
    )
    order = forms.IntegerField(widget=forms.HiddenInput())


VideoOrderFormSet = forms.formset_factory(VideoOrderForm, extra=0)
