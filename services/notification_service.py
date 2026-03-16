import os
import logging
import resend

logger = logging.getLogger(__name__)

# Configure Resend API Key
resend.api_key = os.getenv("RESEND_API_KEY")

class NotificationService:
    @staticmethod
    def send_booking_window_opened_email(user_id: str, package_title: str, package_id: str):
        """
        Sends an email to the user when their dreaming trip becomes bookable using Resend.
        """
        if not resend.api_key:
            logger.warning("RESEND_API_KEY not set. Falling back to log-only notification.")
            logger.info(f"[STUB EMAIL] Subject: Your trip '{package_title}' is now bookable!")
            logger.info(f"[STUB EMAIL] To User: {user_id}")
            return False

        try:
            params = {
                "from": "Ray and Rae <onboarding@resend.dev>", # Default sandbox sender
                "to": [user_id],
                "subject": f"Your trip '{package_title}' is now bookable!",
                "html": f"""
                    <h1>Good news!</h1>
                    <p>The official booking window for your <strong>{package_title}</strong> has opened.</p>
                    <p>We've refreshed the prices and items for you. You can now proceed with official bookings.</p>
                    <p><a href="https://rayandrae.com/package/{package_id}">View your updated holiday plan here</a></p>
                    <p>Happy travels!<br>Ray and Rae</p>
                """
            }

            # Optional: Use custom verified domain if configured
            verified_from = os.getenv("RESEND_FROM_EMAIL")
            if verified_from:
                params["from"] = verified_from

            email = resend.Emails.send(params)
            logger.info(f"[RESEND] Email sent successfully: {email['id']} to {user_id}")
            return True
        except Exception as e:
            logger.error(f"[RESEND] Failed to send email: {e}")
            return False

    @staticmethod
    def send_booking_confirmation(user_email: str, package_data: dict):
        """
        Sends a booking confirmation email with itinerary details and booking links via Resend.
        """
        if not resend.api_key:
            logger.warning("RESEND_API_KEY not set. Falling back to log-only confirmation.")
            return False

        try:
            subject = f"Booking Confirmed: {package_data.get('title', package_data.get('name', 'Your Holiday Package'))}"
            html_content = NotificationService._generate_html_body(package_data)

            params = {
                "from": "Ray and Rae <onboarding@resend.dev>",
                "to": [user_email],
                "subject": subject,
                "html": html_content
            }

            verified_from = os.getenv("RESEND_FROM_EMAIL")
            if verified_from:
                params["from"] = verified_from

            email = resend.Emails.send(params)
            logger.info(f"[RESEND] Booking confirmation sent to {user_email} (ID: {email.get('id')})")
            return True
        except Exception as e:
            logger.error(f"[RESEND] Failed to send booking confirmation email: {e}")
            return False

    @staticmethod
    def _generate_html_body(package):
        """
        Generates a simple HTML body for the booking confirmation email.
        """
        items_html = ""
        for item in package.get('items', []):
            item_status = item.get('status')
            if hasattr(item_status, 'value'):
                item_status = item_status.value
            
            status_desc = "Booked" if item_status == 'booked' else "Pending Action"
            booking_info = ""
            
            meta = item.get('metadata', {})
            if meta.get('booking_link'):
                booking_info = f"<p><a href='{meta['booking_link']}' style='color: #6366f1; text-decoration: none; font-weight: bold;'>Complete Booking Here &rarr;</a></p>"
            elif meta.get('booking_reference'):
                booking_info = f"<p><strong>Ref:</strong> {meta['booking_reference']}</p>"

            items_html += f"""
            <div style='margin-bottom: 20px; padding: 15px; background: #f8fafc; border-radius: 8px;'>
                <h3 style='margin-top: 0;'>{item.get('name')}</h3>
                <p style='color: #666;'>Type: {str(item.get('item_type')).capitalize()} | Price: ${item.get('price', 0.0)}</p>
                {booking_info}
            </div>
            """

            # Handle edge case where name might be 'title'
            package_name = package.get('title', package.get('name', 'Your Holiday Package'))

        return f"""
        <html>
            <body style='font-family: sans-serif; color: #1e293b; line-height: 1.6;'>
                <div style='max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;'>
                    <h1 style='color: #6366f1; border-bottom: 2px solid #6366f1; padding-bottom: 10px;'>Ray and Rae</h1>
                    <h2>Pack your bags! Your holiday is confirmed.</h2>
                    <p>Hi there,</p>
                    <p>Congratulations! Your package <strong>{package_name}</strong> has been successfully processed.</p>
                    
                    <h3>Your Itinerary Summary:</h3>
                    {items_html}
                    
                    <div style='margin-top: 30px; padding: 20px; background: #eef2ff; border-radius: 8px;'>
                        <h4 style='margin-top: 0;'>Next Steps:</h4>
                        <ul>
                            <li>Check your email for official airline/hotel confirmations for the "One-Click" items.</li>
                            <li>For activities and dining, please follow the links above to finalize your slots.</li>
                            <li>Make sure your travel documents are up to date!</li>
                        </ul>
                    </div>
                    
                    <p style='margin-top: 40px; font-size: 0.8em; color: #94a3b8;'>
                        You received this email because you booked a package through Ray and Rae. 
                        Safe travels!
                    </p>
                </div>
            </body>
        </html>
        """
