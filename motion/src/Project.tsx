// The one composition every MIR MOTION render uses: a project = tracks of timed clips.
// Track 0 is the bottom layer. Entrance/exit transitions + per-clip keyframes wrap each scene.
import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {SCENES} from './scenes';
import {Clip, MIR_FONTS, Project, kfAt, transStyle} from './lib';

const FontFaces: React.FC<{base?: string}> = ({base}) => (
	<style>{MIR_FONTS.map((f) => `@font-face{font-family:'MIR-${f}';src:url('${base || 'fonts/'}${f}.woff2') format('woff2');font-display:block}`).join('\n')}</style>
);

const ClipView: React.FC<{c: Clip; proj: Project; durF: number}> = ({c, proj, durF}) => {
	const f = useCurrentFrame();
	const {fps, width} = useVideoConfig();
	const S = SCENES[c.type];
	if (!S) return null;
	const t = f / fps;
	let st: React.CSSProperties = {};
	if (c.trans && c.trans.type !== 'cut' && c.trans.dur > 0) {
		const p = Math.min(1, t / c.trans.dur);
		if (p < 1) st = transStyle(c.trans.type, p, width);
	}
	if (c.out && c.out.type !== 'cut' && c.out.dur > 0) {
		const left = durF / fps - t;
		const p = Math.min(1, left / c.out.dur);
		if (p < 1) st = {...st, ...transStyle(c.out.type, p, width)};
	}
	const k = c.kf || {};
	const x = kfAt(k.x, t, 0);
	const y = kfAt(k.y, t, 0);
	const s = kfAt(k.scale, t, 1);
	const r = kfAt(k.rotate, t, 0);
	const o = kfAt(k.opacity, t, 1);
	const b = kfAt(k.blur, t, 0);
	const has = Object.keys(k).length > 0;
	const kst: React.CSSProperties = has ? {transform: `translate(${x}%, ${y}%) scale(${s}) rotate(${r}deg)`, opacity: o, filter: b ? `blur(${b}px)` : undefined} : {};
	return (
		<AbsoluteFill style={st}>
			<AbsoluteFill style={kst}>
				<S.C p={c.props || {}} proj={proj} durF={durF} />
			</AbsoluteFill>
		</AbsoluteFill>
	);
};

export const MotionProject: React.FC<{project: Project}> = ({project}) => {
	const {fps} = useVideoConfig();
	const p = project;
	return (
		<AbsoluteFill style={{background: p.bg || 'transparent'}}>
			<FontFaces base={p.fontBase} />
			{(p.tracks || []).map((tr, ti) =>
				tr.hide && tr.kind !== 'audio' ? null : tr.mute && tr.kind === 'audio' ? null : (
					<AbsoluteFill key={ti}>
						{(tr.clips || []).map((c) => {
							const from = Math.round((+c.start || 0) * fps);
							const durF = Math.max(1, Math.round((+c.dur || 1) * fps));
							return (
								<Sequence key={c.id} from={from} durationInFrames={durF} layout="none" name={`${c.type}:${c.id}`}>
									<ClipView c={c} proj={p} durF={durF} />
								</Sequence>
							);
						})}
					</AbsoluteFill>
				),
			)}
		</AbsoluteFill>
	);
};
