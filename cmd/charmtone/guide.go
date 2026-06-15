package main

import (
	"fmt"
	"image/color"
	"io"
	"iter"
	"os"
	"strings"

	"charm.land/lipgloss/v2"
	"charm.land/tone"
)

func renderGuide() {
	// Find the longest key name.
	var widestKeyName int
	for _, k := range tone.Keys() {
		if w := lipgloss.Width(k.String()); w > widestKeyName {
			widestKeyName = w
		}
	}

	// Styles.
	hasDarkBG := lipgloss.HasDarkBackground(os.Stdin, os.Stdout)
	lightDark := lipgloss.LightDark(hasDarkBG)
	logo := lipgloss.NewStyle().
		Foreground(tone.Sash).
		Background(tone.Charple).
		Padding(0, 1).
		SetString("Charm™")
	title := lipgloss.NewStyle().
		Foreground(lightDark(tone.Char, tone.Smoke))
	subdued := lipgloss.NewStyle().
		Foreground(lightDark(tone.Squid, tone.Oyster))
	fg := lipgloss.NewStyle().
		MarginLeft(2).
		Width(widestKeyName).
		Align(lipgloss.Right)
	bg := lipgloss.NewStyle().
		Width(8)
	hex := lipgloss.NewStyle().
		Foreground(lightDark(tone.Smoke, tone.Char))
	legend := subdued.
		BorderStyle(lipgloss.RoundedBorder()).
		BorderForeground(tone.Char).
		Padding(0, 2).
		MarginLeft(2)
	primaryMark := lipgloss.NewStyle().
		Foreground(lightDark(tone.Squid, tone.Smoke)).
		SetString(blackCircle)
	secondaryMark := primaryMark.
		Foreground(lightDark(tone.Squid, tone.Oyster)).
		SetString(whiteCircle)
	rightArrowMark := lipgloss.NewStyle().
		Foreground(lightDark(tone.Squid, tone.Oyster)).
		Margin(0, 1).
		SetString(rightArrow)

	var b strings.Builder

	// Render title and description.
	fmt.Fprintf(
		&b,
		"\n  %s %s %s\n\n",
		logo.String(),
		title.Render("tone"),
		subdued.Render("• Formula Guide"),
	)

	// Render a swatch and its metadata.
	renderSwatch := func(w io.Writer, k tone.Key) {
		mark := " "
		switch {
		case k.IsPrimary():
			mark = primaryMark.String()
		case k.IsSecondary():
			mark = secondaryMark.String()
		}
		_, _ = fmt.Fprintf(
			w,
			"%s %s %s %s",
			fg.Foreground(k).Render(k.String()),
			mark,
			bg.Background(k).Render(),
			hex.Render(k.Hex()),
		)
	}

	// Render the main spectrum block in rows of three.
	for i, k := range tone.Spectrum() {
		renderSwatch(&b, k)
		if i%3 == 2 {
			b.WriteRune('\n')
		} else {
			b.WriteRune(' ')
		}
	}

	// Get total block width so far.
	var totalWidth int
	for l := range SplitSeq(b.String(), "\n") {
		if w := lipgloss.Width(l); w > totalWidth {
			totalWidth = w
		}
	}

	// Grayscale block.
	var grays strings.Builder
	for i := tone.Pepper; i <= tone.Soda; i++ {
		k := tone.Keys()[i]
		renderSwatch(&grays, k)
		if i < tone.Soda {
			grays.WriteRune('\n')
		}
	}

	// Get width of grayscale block.
	var grayWidth int
	for l := range SplitSeq(grays.String(), "\n") {
		if w := lipgloss.Width(l); w > grayWidth {
			grayWidth = w
		}
	}

	fmt.Fprint(&b, "\n")

	// Build legend.
	legendBlock := legend.Render(
		strings.Join([]string{
			primaryMark.String() + subdued.Render(" Primary"),
			secondaryMark.String() + subdued.Render(" Secondary"),
		}, "  "),
	)

	// Build gradients.
	var grads strings.Builder
	gap := "  "
	gapWidth := lipgloss.Width(gap)
	{
		fullWidth := (totalWidth - grayWidth) - lipgloss.Width(gap)
		if fullWidth%2 != 0 {
			fullWidth--
		}
		halfWidth := fullWidth / gapWidth

		block := lipgloss.NewStyle().
			Align(lipgloss.Center).
			Width(halfWidth)
		s := subdued.
			Foreground(tone.Squid)

		// Gradient:
		// Hazy -> Blush, Bok -> Zest
		left := blendKeys(halfWidth, tone.Hazy, tone.Blush)
		left += "\n" + block.Render(s.Render("Hazy")+rightArrowMark.String()+s.Render("Blush"))
		right := blendKeys(halfWidth, tone.Bok, tone.Zest)
		right += "\n" + block.Render(s.Render("Bok")+rightArrowMark.String()+s.Render("Zest"))
		fmt.Fprint(&grads, "\n", lipgloss.JoinHorizontal(lipgloss.Top, gap, left, right))

		// Gradient:
		// Uni -> Coral -> Tuna -> Violet -> Malibu -> Turtle
		block = block.Width(fullWidth)
		buf := strings.Builder{}
		fmt.Fprint(&buf, blendKeys(
			fullWidth, tone.Uni,
			tone.Coral, tone.Tuna, tone.Violet,
			tone.Malibu, tone.Turtle,
		))
		fmt.Fprint(
			&buf, "\n",
			block.Render(
				s.Render("Uni")+rightArrowMark.String()+
					s.Render("Coral")+rightArrowMark.String()+
					s.Render("Tuna")+rightArrowMark.String()+
					s.Render("Violet")+rightArrowMark.String()+
					s.Render("Malibu")+rightArrowMark.String()+
					s.Render("Turtle"),
			),
		)
		fmt.Fprint(&grads, "\n\n", lipgloss.JoinHorizontal(lipgloss.Top, gap, buf.String()))
	}

	// Charples block: render below the gradients in the middle column,
	// starting on the same row as Smoke in the grayscale column. Charple
	// appears here a second time and is marked as a brand primary. Butter
	// and Ice live in a third column to the right, next to Jelly and Darple
	// respectively; both are outside the spectrum.
	var charples strings.Builder
	charpleKeys := tone.Charples()
	for i, k := range charpleKeys {
		renderSwatch(&charples, k)
		if i < len(charpleKeys)-1 {
			charples.WriteRune('\n')
		}
	}
	var ends strings.Builder
	renderSwatch(&ends, tone.Butter)
	ends.WriteRune('\n')
	renderSwatch(&ends, tone.Ice)
	charplesRow := lipgloss.JoinHorizontal(lipgloss.Top, charples.String(), " ", ends.String())
	fmt.Fprint(&grads, "\n\n", charplesRow)

	// Join the grayscale column with the gradient/charples column so the
	// first gradient row sits at the top of the grayscale ramp.
	fmt.Fprint(&b, lipgloss.JoinHorizontal(lipgloss.Top, grays.String(), " ", grads.String()))

	fmt.Fprint(&b, "\n\n", legendBlock, "\n\n")

	// Flush.
	_, err := lipgloss.Print(b.String())
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error printing: %v\n", err)
		os.Exit(1)
	}
}

func blendKeys(size int, keys ...tone.Key) string {
	stops := make([]color.Color, len(keys))
	for i := range keys {
		stops[i] = color.Color(keys[i])
	}

	var w strings.Builder
	for _, c := range lipgloss.Blend1D(size, stops...) {
		fmt.Fprint(&w, lipgloss.NewStyle().Background(c).Render(" "))
	}
	return w.String()
}

// SplitSeq returns an iterator over the substrings of string separated by a separator.
//
// This is a Go 1.23 compatible version of strings.Split. Once we're
// supporting Go 1.24 this can be removed in favor of the strings.SplitSeq in
// the standard library.
func SplitSeq(s, sep string) iter.Seq[string] {
	return func(yield func(string) bool) {
		if sep == "" {
			for _, r := range s {
				if !yield(string(r)) {
					return
				}
			}
			return
		}

		start := 0
		for {
			i := strings.Index(s[start:], sep)
			if i == -1 {
				if !yield(s[start:]) {
					return
				}
				break
			}
			if !yield(s[start : start+i]) {
				return
			}
			start += i + len(sep)
		}
	}
}
