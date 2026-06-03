// AudioWorklet processor that captures mic input and emits 24 kHz
// mono PCM16 frames. The host AudioContext runs at 24 kHz so we don't
// need to resample here — the browser does it transparently when the
// context rate doesn't match the hardware rate.
class PCMRecorder extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = [];
    // 480 samples @ 24 kHz = 20 ms — a standard Voice Live frame size
    this.frameSize = 480;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    for (let i = 0; i < channel.length; i++) {
      this.buffer.push(channel[i]);
    }

    while (this.buffer.length >= this.frameSize) {
      const slice = this.buffer.slice(0, this.frameSize);
      this.buffer = this.buffer.slice(this.frameSize);

      const pcm = new Int16Array(this.frameSize);
      for (let i = 0; i < this.frameSize; i++) {
        const s = Math.max(-1, Math.min(1, slice[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor("pcm-recorder", PCMRecorder);
