# UX And Accessibility Recommendations

This note translates established ergonomics and accessibility guidance into concrete TriageDesk improvements.

## Recommended Improvements

1. **Keep system status visible.** Live logs, richer subagent states, and explicit handoff profiles reduce uncertainty during long-running agent tasks.

2. **Prefer recognition over recall.** Buttons and cards should say what they do in plain language, not rely only on icons or internal runner names.

3. **Reduce cognitive load.** Progressive disclosure, expandable cards, and compact recent-activity panels let users inspect details when needed without overloading the main screen.

4. **Improve target size and focus visibility.** Primary dispatch controls should be large enough to select comfortably, and future work should verify keyboard navigation and visible focus states.

5. **Measure review burden.** TriageCore records `human_review_minutes` and can now store an optional `review_workload` label so studies can compare elapsed review time with perceived difficulty.

## Supporting Sources

- W3C WCAG 2.2: target size, focus appearance, and understandable/operable interface guidance. <https://www.w3.org/WAI/WCAG22/Understanding/>
- W3C WAI cognitive accessibility guidance: reduce memory burden, make purpose clear, and support users through task flows. <https://www.w3.org/WAI/cognitive/>
- NASA Task Load Index: supports measuring perceived workload alongside task performance. <https://www.nasa.gov/human-systems-integration-division/nasa-task-load-index-tlx/>
- Cognitive Load Theory: supports progressive disclosure and reducing unnecessary information processing. <https://link.springer.com/article/10.1007/s10648-010-9145-4>
- Nielsen usability heuristics: supports visibility of system status, recognition rather than recall, and clear user control. <https://www.nngroup.com/articles/ten-usability-heuristics/>
