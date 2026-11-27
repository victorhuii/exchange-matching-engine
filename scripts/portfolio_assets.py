"""Generate exportable visuals from actual engine output and recorded benchmarks."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/assets';OUT.mkdir(exist_ok=True)
BENCH=json.loads((ROOT/'docs/benchmark.json').read_text())
DEMO=json.loads((ROOT/'docs/demo/session.json').read_text())
REPLAY=json.loads((ROOT/'docs/demo/replay.json').read_text())
INK,MUTED,BLUE,GREEN,RED,LINE='#202b36','#657180','#305f86','#36765e','#ad514d','#dde3e8'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'text.color':INK,'axes.labelcolor':MUTED,
    'xtick.color':MUTED,'ytick.color':MUTED,'axes.spines.top':False,'axes.spines.right':False,
    'axes.edgecolor':LINE,'figure.facecolor':'white','axes.facecolor':'white','svg.fonttype':'none'})

def save(fig,name):
    fig.savefig(OUT/f'{name}.png',dpi=160,facecolor='white')
    fig.savefig(OUT/f'{name}.svg',facecolor='white')
    svg=OUT/f'{name}.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)

def heading(fig,title,subtitle):
    fig.text(.06,.935,title,fontsize=23 if len(title)<45 else 20,weight='bold')
    fig.text(.06,.89,subtitle,fontsize=11,color=MUTED)

def cover():
    fig=plt.figure(figsize=(8,4));ax=fig.add_axes([0,0,1,1]);ax.axis('off')
    fig.text(.075,.80,'Exchange',fontsize=38,weight='bold')
    fig.text(.075,.66,'Matching Engine',fontsize=38,weight='bold')
    fig.text(.075,.53,'C++20 · deterministic matching · durable recovery',fontsize=13,color=MUTED)
    ax.plot([.075,.925],[.44,.44],color=LINE,lw=1,transform=ax.transAxes)
    sample=BENCH['results']['memory']
    for x,value,label in [(.075,f"{sample['commands']:,}",'benchmark commands'),(.39,str(sample['trades']),'recorded trades'),(.71,'FIFO','price-time priority')]:
        fig.text(x,.28,value,fontsize=26,color=BLUE)
        fig.text(x,.18,label,fontsize=10,color=MUTED)
    fig.text(.075,.065,'Local simulation · synthetic participants · no live orders',fontsize=10,color=MUTED)
    save(fig,'portfolio-cover')

def box(ax,x,y,w,h,title,body):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.01,rounding_size=.012',edgecolor=LINE,facecolor='#f2f6fa',lw=1))
    ax.text(x+.025,y+h-.065,title,fontsize=13,weight='bold',color=BLUE)
    ax.text(x+.025,y+h-.125,body,fontsize=11,va='top',linespacing=1.7)

def matching():
    fills=DEMO['events'][2]['result']['trades']
    assert [(t['maker'],t['quantity']) for t in fills]==[('alice-ask',5),('bob-ask',2)]
    fig=plt.figure(figsize=(10,6.25));ax=fig.add_axes([.06,.12,.88,.68]);ax.axis('off')
    heading(fig,'Price-time matching','Generated from the C++ engine · prices in ticks, quantities in units')
    box(ax,.01,.52,.43,.38,'Resting sells at 10,001','Alice · 5 units · first arrival\nBob · 4 units · second arrival')
    box(ax,.55,.52,.43,.38,'Incoming buy at 10,001','Carol · 7 units\nBetter price, then earliest arrival')
    box(ax,.01,.06,.43,.35,'Two executions','Alice sells 5 to Carol\nBob sells 2 to Carol')
    box(ax,.55,.06,.43,.35,'Remaining order','Bob · 2 sell units at 10,001\nDave IOC at 10,000: 3 cancelled')
    fig.text(.06,.075,f"Recovery proof: snapshot at command {DEMO['snapshot_sequence']}, cancel applied at {DEMO['recovered_sequence']}, identical recovered state.",fontsize=11,color=BLUE)
    fig.text(.06,.03,'Actual engine trace with fictional participants, not a browser screenshot.',fontsize=9,color=MUTED)
    save(fig,'matching-demo')

def book():
    event=max((e for e in REPLAY if e['state']['bids'] and e['state']['asks']),key=lambda e:len(e['state']['orders']))
    state=event['state']
    fig,ax=plt.subplots(figsize=(10,6.25));fig.subplots_adjust(left=.10,right=.95,top=.77,bottom=.20)
    heading(fig,'The resulting order book',f"Seeded synthetic flow · after command {state['sequence']} · {len(state['orders'])} resting orders")
    for side,color,label in [('bids',GREEN,'Buy quantity'),('asks',RED,'Sell quantity')]:
        levels=state[side]
        ax.bar([l['price'] for l in levels],[l['quantity'] for l in levels],width=.75,color=color,alpha=.8,label=label)
    ax.set_xlabel('Limit price (integer ticks)');ax.set_ylabel('Displayed quantity (units)')
    ax.ticklabel_format(axis='x',style='plain',useOffset=False)
    ax.grid(axis='y',color=LINE,alpha=.5);ax.set_axisbelow(True)
    ax.legend(frameon=False)
    fig.text(.06,.09,f"Best bid {state['bids'][0]['price']} · best ask {state['asks'][0]['price']} · spread {state['asks'][0]['price']-state['bids'][0]['price']} ticks",fontsize=11,color=BLUE)
    fig.text(.06,.035,'Generated from recorded C++ state. This is a data visualization, not a browser screenshot or market-data feed.',fontsize=9,color=MUTED)
    save(fig,'order-book-demo')

def benchmark():
    fig,axes=plt.subplots(1,2,figsize=(10,6.25));fig.subplots_adjust(left=.09,right=.95,top=.75,bottom=.31,wspace=.65)
    heading(fig,'Matching and durability, measured separately','Single recorded local run · 2,000 synthetic commands · no warmup')
    labels=['Memory-only','Journal + fsync'];colors=[BLUE,'#7891a7']
    results=[BENCH['results']['memory'],BENCH['results']['durable']]
    axes[0].bar(labels,[r['commands_per_second'] for r in results],color=colors,width=.5)
    axes[0].set_ylabel('Commands per second');axes[0].ticklabel_format(axis='y',style='plain')
    for i,r in enumerate(results):axes[0].text(i,r['commands_per_second']*1.025,f"{r['commands_per_second']:,.0f}",ha='center',fontsize=11)
    axes[0].set_ylim(0,max(r['commands_per_second'] for r in results)*1.22)
    x=np.arange(3)
    for i,(label,r,color) in enumerate(zip(labels,results,colors)):
        axes[1].bar(x+(i-.5)*.35,[r['latency_us'][p] for p in ['p50','p95','p99']],width=.32,label=label,color=color)
    axes[1].set_xticks(x,['p50','p95','p99']);axes[1].set_ylabel('Service time (µs)');axes[1].set_yscale('log')
    axes[1].legend(frameon=False,fontsize=9,loc='lower center',bbox_to_anchor=(.5,-.43))
    for ax in axes:ax.grid(axis='y',color=LINE,alpha=.5);ax.set_axisbelow(True)
    fig.text(.06,.135,'Includes validation, matching, response serialization and deduplication; durable path adds journal fsync.',fontsize=9,color=MUTED)
    fig.text(.06,.09,'Excludes parsing, participant generation, Python, IPC, HTTP and exchange queueing. Small book: at most 30 orders.',fontsize=9,color=MUTED)
    fig.text(.06,.04,'macOS 15.7.3 · arm64 · Apple clang 17 · C++20 -O3. Generated result figure, not a UI screenshot.',fontsize=9,color=MUTED)
    save(fig,'benchmark-demo')

if __name__=='__main__':
    cover();matching();book();benchmark()
    print('Generated four PNG and four SVG portfolio visuals.')
