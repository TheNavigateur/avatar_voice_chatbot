import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.environ.get("SMTP_PORT", 587))
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_pass = os.environ.get("SMTP_PASS")
        
        # Template environment
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'emails')
        if not os.path.exists(template_dir):
            os.makedirs(template_dir, exist_ok=True)
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))

    def send_booking_confirmation(self, user_email: str, package_data: dict):
        """
        Sends a booking confirmation email with itinerary details and booking links.
        """
        if not all([self.smtp_user, self.smtp_pass]):
            logger.warning("Email Service: SMTP credentials not set. Skipping email.")
            return False

        try:
            subject = f"Booking Confirmed: {package_data.get('name', 'Your Holiday Package')}"
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"Ray and Rae <{self.smtp_user}>"
            msg["To"] = user_email

            # Simplified HTML content (would use a proper Jinja2 template in a real app)
            html_content = self._generate_html_body(package_data)
            msg.attach(MIMEText(html_content, "html"))

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.smtp_user, user_email, msg.as_string())
            
            logger.info(f"Booking confirmation email sent to {user_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send booking confirmation email: {e}")
            return False

    def _generate_html_body(self, package):
        """
        Generates a simple HTML body for the email.
        """
        items_html = ""
        for item in package.get('items', []):
            status_desc = "Booked" if item.get('status') == 'booked' else "Pending Action"
            booking_info = ""
            if item.get('metadata', {}).get('booking_link'):
                booking_info = f"<p><a href='{item['metadata']['booking_link']}' style='color: #6366f1; text-decoration: none; font-weight: bold;'>Complete Booking Here &rarr;</a></p>"
            elif item.get('metadata', {}).get('booking_reference'):
                booking_info = f"<p><strong>Ref:</strong> {item['metadata']['booking_reference']}</p>"

            items_html += f"""
            <div style='margin-bottom: 20px; padding: 15px; background: #f8fafc; border-radius: 8px;'>
                <h3 style='margin-top: 0;'>{item.get('name')}</h3>
                <p style='color: #666;'>Type: {item.get('item_type').capitalize()} | Price: {item.get('price')}</p>
                {booking_info}
            </div>
            """

        return f"""
        <html>
            <body style='font-family: sans-serif; color: #1e293b; line-height: 1.6;'>
                <div style='max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;'>
                    <h1 style='color: #6366f1; border-bottom: 2px solid #6366f1; padding-bottom: 10px;'>Ray and Rae</h1>
                    <h2>Pack your bags! Your holiday is confirmed.</h2>
                    <p>Hi there,</p>
                    <p>Congratulations! Your package <strong>{package.get('name')}</strong> has been successfully processed.</p>
                    
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
