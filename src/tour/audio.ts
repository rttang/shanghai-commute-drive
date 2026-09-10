/** Small, synthesised EV/road ambience; no remote audio or autoplay request. */
export class DriveAudio {
  private context?:AudioContext;private master?:GainNode;private motor?:OscillatorNode;private motorGain?:GainNode;private roadGain?:GainNode;private filter?:BiquadFilterNode;
  muted=false;
  async start(){
    if(!this.context){
      const c=this.context=new AudioContext(),master=this.master=c.createGain();master.gain.value=.3;master.connect(c.destination);
      const motor=this.motor=c.createOscillator();motor.type='triangle';
      const gain=this.motorGain=c.createGain();gain.gain.value=0;motor.connect(gain);gain.connect(master);motor.start();
      const buffer=c.createBuffer(1,c.sampleRate*2,c.sampleRate),data=buffer.getChannelData(0);
      let previous=0;for(let i=0;i<data.length;i++){previous=.96*previous+.04*(Math.random()*2-1);data[i]=previous*5;}
      const noise=c.createBufferSource();noise.buffer=buffer;noise.loop=true;
      const filter=this.filter=c.createBiquadFilter();filter.type='lowpass';filter.frequency.value=300;
      const road=this.roadGain=c.createGain();road.gain.value=0;noise.connect(filter);filter.connect(road);road.connect(master);noise.start();
    }
    if(this.context.state==='suspended')await this.context.resume();
  }
  update(speed:number,running:boolean,tunnel:boolean){
    const c=this.context;if(!c||!this.motor||!this.motorGain||!this.roadGain||!this.filter||!this.master)return;
    const v=Math.abs(speed);
    this.master.gain.setTargetAtTime(this.muted||!running?0:.3,c.currentTime,.15);
    this.motor.frequency.setTargetAtTime(65+v*17,c.currentTime,.12);
    this.motorGain.gain.setTargetAtTime(v>.15?.012+v*.0006:0,c.currentTime,.12);
    this.roadGain.gain.setTargetAtTime(Math.min(.12,v*.004)*(tunnel?1.4:1),c.currentTime,.2);
    this.filter.frequency.setTargetAtTime(200+v*65,c.currentTime,.3);
  }
  impact(strength:number){
    const c=this.context;if(!c||!this.master||this.muted)return;
    const buffer=c.createBuffer(1,c.sampleRate*.22,c.sampleRate),d=buffer.getChannelData(0);
    for(let i=0;i<d.length;i++)d[i]=(Math.random()*2-1)*Math.exp(-i/(c.sampleRate*.035));
    const source=c.createBufferSource();source.buffer=buffer;
    const gain=c.createGain();gain.gain.value=Math.min(.6,strength/25);source.connect(gain);gain.connect(this.master);source.start();source.onended=()=>{source.disconnect();gain.disconnect();};
  }
  horn(){
    const c=this.context;if(!c||!this.master||this.muted)return;
    for(const frequency of [350,440]){const o=c.createOscillator(),g=c.createGain();o.frequency.value=frequency;g.gain.setValueAtTime(.07,c.currentTime);g.gain.exponentialRampToValueAtTime(.001,c.currentTime+.35);o.connect(g);g.connect(this.master);o.start();o.stop(c.currentTime+.36);o.onended=()=>{o.disconnect();g.disconnect();};}
  }
}
