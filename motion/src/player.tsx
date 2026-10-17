// Browser bundle for Motion Studio: window.MirMotion.mount(el, project, opts) → live @remotion/player preview.
import React from 'react';
import {createRoot, Root as RRoot} from 'react-dom/client';
import {Player, PlayerRef} from '@remotion/player';
import {MotionProject} from './Project';
import {Project, TEXT_ANIMS, TRANSITIONS, projectDuration} from './lib';
import {schema} from './scenes';

type Opts = {onFrame?: (f: number) => void; loop?: boolean; controls?: boolean};
let root: RRoot | null = null;
let ref: React.RefObject<PlayerRef> = React.createRef();

const View: React.FC<{project: Project; opts: Opts}> = ({project, opts}) => {
	const fps = Math.max(1, +project.fps || 30);
	React.useEffect(() => {
		const p = ref.current;
		if (!p || !opts.onFrame) return;
		const h = (e: any) => opts.onFrame!(e.detail.frame);
		p.addEventListener('frameupdate', h);
		p.addEventListener('seeked', h);
		return () => {
			p.removeEventListener('frameupdate', h);
			p.removeEventListener('seeked', h);
		};
	}, [opts]);
	return (
		<Player
			ref={ref}
			component={MotionProject as any}
			inputProps={{project}}
			durationInFrames={Math.max(1, Math.round(projectDuration(project) * fps))}
			fps={fps}
			compositionWidth={(+project.w || 1280) & ~1}
			compositionHeight={(+project.h || 720) & ~1}
			style={{width: '100%', height: '100%'}}
			controls={opts.controls ?? false}
			loop={opts.loop ?? false}
			acknowledgeRemotionLicense
			clickToPlay={false}
			spaceKeyToPlayOrPause={false}
		/>
	);
};

let cur: {el: HTMLElement; opts: Opts} | null = null;
(window as any).MirMotion = {
	schema: schema(),
	textAnims: TEXT_ANIMS,
	transitions: TRANSITIONS,
	duration: projectDuration,
	mount(el: HTMLElement, project: Project, opts: Opts = {}) {
		if (!root || !cur || cur.el !== el) {
			root = createRoot(el);
			cur = {el, opts};
		}
		cur.opts = opts;
		root.render(<View project={project} opts={opts} />);
	},
	update(project: Project) {
		if (root && cur) root.render(<View project={project} opts={cur.opts} />);
	},
	play: () => ref.current?.play(),
	pause: () => ref.current?.pause(),
	toggle: () => ref.current?.toggle(),
	seek: (f: number) => ref.current?.seekTo(Math.max(0, Math.round(f))),
	frame: () => ref.current?.getCurrentFrame() ?? 0,
	playing: () => ref.current?.isPlaying() ?? false,
};
