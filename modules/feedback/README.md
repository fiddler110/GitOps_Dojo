# feedback

End-of-class survey. Students get a **Feedback** card (four 1-5 ratings and a comment; they can resubmit to
change it). The facilitator's **Feedback** admin tab shows means, counts per rating, the comments, and a CSV/JSON
export. Answers carry no username to the facilitator; the username only keeps it to one answer per student.

List `feedback` in `MODULES=`. No settings beyond `FEEDBACK_MEM_LIMIT`. Answers live in the `feedback_data`
volume. `./dojo stop` saves them to `results/<date>_<time>_<workshop>/feedback.csv/json` before deleting the volume (with
the scores, roster and a manifest of what ran and when); `./dojo export-feedback` does it on demand.

Questions are fixed in `server.py` (`QUESTIONS`) and mirrored in `static/feedback.js`.
