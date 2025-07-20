
# Equipment Booking App

This is a Django-based application for booking equipment. It provides functionality for users to view, create, edit, and delete bookings based on their permissions. The app also includes a user messaging system and an admin-managed notice board.

## Features

-   **User Authentication**: Users can sign up, log in, and log out securely.
-   **Equipment Booking**: Users can book various types of equipment, specifying start and end times, reasons, project numbers, and usage locations.
    -   Superusers can create, edit, and delete any booking.
    -   Regular users can create bookings and edit their own future bookings.
-   **User Profiles**: Users can manage their profiles, including phone numbers, work addresses, and job roles.
-   **Messaging System**: Users can send messages to superadmins, and superadmins can respond via the inbox.
-   **Notice Board**: Admins can post system-wide notices that users can view on the home page.
-   **Past and Upcoming Bookings**: Users can view their past and upcoming bookings, while superusers can see all bookings.

## Installation

1.  **Clone the repository**:
    
 
  
    `git clone https://github.com/CurtisHai/equipment-booking-app.git
    cd equipment-booking-app` 
    
2.  **Create a virtual environment** (optional but recommended):
    

    
    `python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate` 
    
3.  **Install the dependencies**:
    

    
    `pip install -r requirements.txt` 
    
4.  **Run migrations**:
   

    
    `python manage.py migrate` 
    
5.  **Create a superuser** to manage the app:
    

    
    `python manage.py createsuperuser` 
    
6.  **Run the development server**:
    
    
    
    `python manage.py runserver` 
    
7.  **Access the app** in your browser:
    
 
    
    `http://127.0.0.1:8000/` 
    




