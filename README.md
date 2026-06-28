# EasyTeaching

A Python-based desktop application developed as a Computer Science Internal Assessment (IA) to streamline administrative workflows and grading systems for educators.

## Features
* Automated administrative task management.
* User-friendly interface designed for faculty members.
* Dynamic data processing pipelines.

## Known Issues & Future Optimization
* **Notification Module Loop:** The notification system successfully fires on the initial trigger. However, due to an unthrottled event loop/state-reset condition, it occasionally enters a rapid firing cycle. 
* **Planned Fix:** Implement an explicit state-flag system (`notification_sent = True`) or absolute timestamp validation to prevent rapid recurrence within the same minute frame.
