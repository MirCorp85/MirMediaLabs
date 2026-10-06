"""What each model and ComfyUI node is actually doing, in plain English, for the MUSE bubble's live line."""

MODEL = {
    "h3": "MiniMax H3 video",
    "music3": "MiniMax Music 3",
    "qimg": "Qwen Image",
    "ace": "ACE-Step audio",
    "llama": "MUSE · Llama 3.1",
}

# (substring of the node class, what it means) - first match wins, so specific names go first
NODES = [
    ("MiniMaxMusic3TextEncode", "composing the song structure from the lyrics and style"),
    ("TextEncodeAceStep", "writing the music codes from the prompt"),
    ("KSamplerAdvanced", "denoising · each step sharpens the result"),
    ("SamplerCustomAdvanced", "denoising · each step sharpens the result"),
    ("SamplerCustom", "denoising · each step sharpens the result"),
    ("KSampler", "denoising · each step sharpens the result"),
    ("VAEDecodeTiled", "decoding the latents into pixels, tile by tile"),
    ("VAEDecodeAudio", "decoding the latents into sound"),
    ("VAEDecode", "decoding the latents into pixels"),
    ("VAEEncode", "reading the input into latent space"),
    ("CLIPTextEncode", "reading the prompt with the text encoder"),
    ("TextEncode", "reading the prompt with the text encoder"),
    ("LoraLoader", "attaching the LoRA style"),
    ("UNETLoader", "loading the diffusion model into VRAM"),
    ("CheckpointLoader", "loading the model checkpoint"),
    ("CLIPLoader", "loading the text encoder"),
    ("VAELoader", "loading the VAE"),
    ("Loader", "loading model weights"),
    ("LoadImage", "loading your reference image"),
    ("LoadVideo", "loading your reference video"),
    ("LoadAudio", "loading your reference audio"),
    ("EmptyLatent", "preparing a blank latent canvas"),
    ("ModelSampling", "setting the noise schedule"),
    ("BasicScheduler", "setting the noise schedule"),
    ("RandomNoise", "seeding the noise"),
    ("Guider", "setting the prompt guidance"),
    ("Upscale", "upscaling"),
    ("CreateVideo", "assembling the frames into a video"),
    ("SaveVideo", "saving the video"),
    ("SaveAudio", "saving the audio"),
    ("SaveImage", "saving the image"),
    ("Save", "saving"),
]


def node(cls):
    c = (cls or "").lower()
    return next((w for k, w in NODES if k.lower() in c), (cls or "working"))


def eta(sec):
    if sec is None:
        return ""
    return "~%d min left" % round(sec / 60) if sec >= 90 else "~%d s left" % sec
