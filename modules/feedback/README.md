# feedback

End-of-class survey. Students get a **Feedback** card (four 1-5 ratings and a comment; they can resubmit to
change it). The facilitator's **Feedback** admin tab shows means, counts per rating, the comments, and a CSV/JSON
export. Answers carry no username to the facilitator; the username only keeps it to one answer per student.

List `feedback` in `MODULES=`. No settings beyond `FEEDBACK_MEM_LIMIT`. Answers live in the `feedback_data`
volume and go with `./dojo stop`: export first if you want to keep them.

Questions are fixed in `server.py` (`QUESTIONS`) and mirrored in `static/feedback.js`.
