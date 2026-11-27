"""Deliberately simple independent list-based oracle; not the production core."""
from copy import deepcopy
from collections import defaultdict
import random

class Reference:
    def __init__(self):
        self.sequence = 0
        self.orders = []
        self.used = set()
        self.requests = {}
        self.trades = []
        self.balances = defaultdict(lambda: dict(cash=0, inventory=0))

    def submit(self, c):
        if c['request_id'] in self.requests:
            old, result = self.requests[c['request_id']]
            if old != c:
                raise ValueError('conflicting request')
            return deepcopy(result)
        self.sequence += 1
        filled, cancelled, resting, trades = 0, 0, 0, []
        if c['type'] == 'cancel':
            maker = next(o for o in self.orders if o['order_id'] == c['order_id'])
            cancelled = maker['quantity']
            self.orders.remove(maker)
        else:
            self.used.add(c['order_id'])
            left = c['quantity']
            while left:
                choices = [o for o in self.orders if o['side'] != c['side'] and
                           (o['price'] <= c['price'] if c['side']=='buy' else o['price'] >= c['price'])]
                if not choices:
                    break
                price = (min if c['side']=='buy' else max)(o['price'] for o in choices)
                maker = next(o for o in self.orders if o in choices and o['price']==price)
                size = min(left, maker['quantity'])
                buyer = c['participant'] if c['side']=='buy' else maker['participant']
                seller = maker['participant'] if c['side']=='buy' else c['participant']
                trade = dict(trade_id=len(self.trades)+1, sequence=self.sequence, price=price, quantity=size,
                             buyer=buyer, seller=seller, maker=maker['order_id'], taker=c['order_id'])
                self.trades.append(trade); trades.append(trade)
                self.balances[buyer]['cash'] -= size*price
                self.balances[buyer]['inventory'] += size
                self.balances[seller]['cash'] += size*price
                self.balances[seller]['inventory'] -= size
                maker['quantity'] -= size; left -= size; filled += size
                if not maker['quantity']:
                    self.orders.remove(maker)
            if c.get('tif')=='IOC':
                cancelled=left
            elif left:
                resting=left
                self.orders.append(dict(order_id=c['order_id'],participant=c['participant'],side=c['side'],
                                        price=c['price'],quantity=left,sequence=self.sequence))
        result = dict(sequence=self.sequence,order_id=c['order_id'],filled=filled,resting=resting,cancelled=cancelled,trades=trades)
        self.requests[c['request_id']] = (deepcopy(c),deepcopy(result))
        return result

    def state(self):
        book = {}
        for side, name, reverse in [('buy','bids',True),('sell','asks',False)]:
            levels=defaultdict(lambda: dict(quantity=0,orders=0))
            for o in self.orders:
                if o['side']==side:
                    levels[o['price']]['quantity']+=o['quantity']
                    levels[o['price']]['orders']+=1
            book[name]=[dict(price=p,**levels[p]) for p in sorted(levels,reverse=reverse)]
        return dict(sequence=self.sequence,**book,orders=deepcopy(self.orders),trades=deepcopy(self.trades),
                    balances={name:dict(cash=str(b['cash']),inventory=b['inventory']) for name,b in self.balances.items()})

def flow(count=100, seed=42):
    rng=random.Random(seed); ref=Reference(); stream=[]
    for i in range(count):
        key=f'flow-{i+1}'
        if ref.orders and rng.random()<.15:
            maker=rng.choice(ref.orders)
            c=dict(type='cancel',request_id=key,order_id=maker['order_id'],participant=maker['participant'])
        else:
            c=dict(type='order',request_id=key,order_id=key,participant=f'agent-{rng.randrange(4)}',
                   side=rng.choice(['buy','sell']),price=rng.randint(9995,10005),quantity=rng.randint(1,8),
                   tif='IOC' if rng.random()<.35 else 'GTC')
        ref.submit(c);stream.append(c)
    return stream
