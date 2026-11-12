# Accessibility (TMS-NF-004, WCAG 2.1 AA)

Automated checks (`tests/unit/ui/test_accessibility_wcag.py`, TC-UX-01) run on every page: page language and title, landmarks, a skip link as
the first control, a label on every field, heading order, table header scope, button names, and colour contrast calculated from the style
sheet for the light and dark themes (text 4.5:1, borders and focus ring 3:1). The audit found and we fixed one defect: the light-theme border
colour was 2.54:1.

Manual checks still to record before sign-off: keyboard-only walk through each page, a screen reader pass (NVDA or VoiceOver) on the operator
console, 200% zoom, and a live-region check that new incident alerts are announced (`role="alert"` on the alerts panel).
