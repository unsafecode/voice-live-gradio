// AudioWorklet processor that plays back PCM16 chunks sent from the
// main thread. The chunks are queued and drained at the host
// AudioContext rate (which we pin to 24 kHz).
class PCMPlayer extends AudioWorkletProcessor {
  constructor() {
    super();
    /** @type {Float32Array[]} */
    this.queue = [];
    this.port.onmessage = (event) => {
      const data = event.data;
      if (data === "clear") {
        this.queue = [];
        return;
      }
      // data is an ArrayBuffer of Int16Array PCM
      const i16 = new Int16Array(data);
      const f32 = new Float32Array(i16.length);
      for (let i = 0; i < i16.length; i++) {
        f32[i] = i16[i] / 0x8000;
      }
      this.queue.push(f32);
    };
  }

  process(_inputs, outputs) {
    const out = outputs[0][0];
    let written = 0;
    while (written < out.length) {
      if (this.queue.length === 0) {
        for (let i = written; i < out.length; i++) out[i] = 0;
        return true;
      }
      const head = this.queue[0];
      const take = Math.min(head.length, out.length - written);
      out.set(head.subarray(0, take), written);
      written += take;
      if (take === head.length) {
        this.queue.shift();
      } else {
        this.queue[0] = head.subarray(take);
      }
    }
    return true;
  }
}

registerProcessor("pcm-player", PCMPlayer);
