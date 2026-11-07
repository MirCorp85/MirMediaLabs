// Signature style tokens: one source of truth for every shared Signature component.
// Two modes share one accent and one type family: STUDIO (cinematic hero moments) and HUD (blueprint breakdowns).
import {Easing, interpolate} from 'remotion';

export const C = {
	amber: '#FFB547', // the ONE highlight per shot, both modes
	ink: '#F2F6FA',
	red: '#FF5A5A', // warnings / "doubtful" only
	// Oct 17: user prefers style B → diagrams are drawn in B's language (silver line art on the charcoal showroom).
	// Keys keep their old names so every component re-skins from here; the navy/cyan HUD look is retired.
	cyan: '#E6EBF0', // schematic line art (silver-white)
	cyanSoft: '#B8C0CA',
	hudLabel: '#8C939C',
	hudBg0: '#08080A',
	hudBg1: '#2A2A30',
	studio0: '#08080A',
	studio1: '#3A3A40',
	quiet: '#9AA0A8',
};

export const F = {
	head: '"Bahnschrift", "Segoe UI", sans-serif', // headlines + captions (both modes)
	num: '"Segoe UI Variable Display", "Segoe UI Variable", "Segoe UI", sans-serif', // giant thin numerals
	mono: '"Consolas", "Cascadia Mono", monospace', // HUD labels + spec values
};

export const T = {numeral: 250, headline: 84, caption: 40, label: 26, mono: 24};

export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const easeIn = Easing.bezier(0.22, 1, 0.36, 1);
export const easeOut = Easing.in(Easing.cubic);

// 0→1 ramp over [a, a+d] seconds, given the current time in seconds
export const ramp = (t: number, a: number, d: number, e = easeIn) => interpolate(t, [a, a + d], [0, 1], {...clamp, easing: e});
