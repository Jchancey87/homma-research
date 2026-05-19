class VWAPCalculator:
    """
    In-memory VWAP accumulator per ticker session.
    """
    def __init__(self):
        self.total_value = 0.0
        self.total_volume = 0
    
    def add_trade(self, price, volume):
        self.total_value += price * volume
        self.total_volume += volume
    
    @property
    def vwap(self):
        if self.total_volume == 0:
            return 0.0
        return self.total_value / self.total_volume

    def reset(self):
        self.total_value = 0.0
        self.total_volume = 0
