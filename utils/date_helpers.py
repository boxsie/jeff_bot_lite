from datetime import datetime

class DateCountdown:
    def __init__(self, days: int, hours: int, mins: int, total_seconds: int, is_today: bool):
        self.days = days
        self.hours = hours
        self.mins = mins
        self.total_seconds = total_seconds
        self.is_today = is_today       
        

def _get_delta(target_month, target_day):
    today = datetime.today()
    target_date = datetime(year=today.year, month=target_month, day=target_day)
    delta = target_date - today    
    
    if delta.days < -1:
        target_date = datetime(year=today.year + 1, month=target_month, day=target_day)
        delta = target_date - today
  
    return (delta, target_date)


def get_next_occurance(target_month, target_day):
    delta, target_date = _get_delta(target_month, target_day)
    
    return DateCountdown(
        days=delta.days,
        hours=int(delta.seconds // (60 * 60)),
        mins=int((delta.seconds // 60) % 60),
        total_seconds=delta.total_seconds(),
        is_today=datetime.now().date() == target_date.date()
    )