# Mobile follow-ups

Desktop performance and the tour redesign (anchored callout, no overlay or blur) landed first. Still to do on phones:

- Tour callout: on phones it is still a bottom sheet (max 38 vh). Check that the new `.hl` highlight (a 2 px ring plus a
  dim from a large box-shadow) does not leave a visible seam at the sheet edge, and that Collapse / Hide still work with
  the new Esc and arrow-key handlers (no keyboard on a phone, so add swipe or tap targets for Back/Next at 44 px).
- The welcome card is now a small bottom card (`.welcome-mini`); confirm it does not sit on top of the ☰ menu sheet or
  the "Tour 2/4" chip.
- Globe on phones: rendering is capped at 30 fps and only while visible. Re-check that the collision simulation still
  looks smooth when scrubbing on a mid-range phone, and consider a lower `devicePixelRatio` cap (1) there.
- Event page tab bar: the sticky offsets (`top: 50px` and `100px`) are hard-coded for the 8 px top bar; verify with the
  snapshot badge and the Live banner showing, which add height.
- Next 24 h: the timeline strip scrolls horizontally; add a vertical list alternative with time bars.
- Insights fleet globe: tap-to-open needs two taps; add a visible hint.
- Landscape (844x390): hero and decision row take the whole screen; fold the decision row under a button there.
