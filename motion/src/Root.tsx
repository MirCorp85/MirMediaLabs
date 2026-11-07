import React from 'react';
import {Composition, Still} from 'remotion';
import {MotionProject} from './Project';
import {Project, projectDuration} from './lib';

const DEMO: Project = {
	w: 1280,
	h: 720,
	fps: 30,
	tracks: [
		{kind: 'scene', clips: [{id: 'a', type: 'title', start: 0, dur: 4, props: {text: 'MIR MOTION', sub: 'MIR MEDIA LABS', anim: 'word-pop'}}]},
	],
};

export const Root: React.FC = () => (
	<>
	<Composition
		id="Project"
		component={MotionProject as any}
		defaultProps={{project: DEMO}}
		durationInFrames={120}
		fps={30}
		width={1280}
		height={720}
		calculateMetadata={({props}: any) => {
			const p: Project = props.project;
			const fps = Math.max(1, Math.min(60, +p.fps || 30));
			return {fps, width: (+p.w || 1280) & ~1, height: (+p.h || 720) & ~1, durationInFrames: Math.max(1, Math.round(projectDuration(p) * fps))};
		}}
	/>

	</>
);
