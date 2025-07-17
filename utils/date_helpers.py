import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger('discord.date_helpers')

class DateCountdown:
    def __init__(self, days: int, hours: int, mins: int, total_seconds: float, is_today: bool):
        try:
            # Validate inputs
            if not isinstance(days, int) or days < 0:
                logger.warning(f"Invalid days value: {days}")
                days = max(0, int(days)) if days is not None else 0
                
            if not isinstance(hours, int) or hours < 0:
                logger.warning(f"Invalid hours value: {hours}")
                hours = max(0, int(hours)) if hours is not None else 0
                
            if not isinstance(mins, int) or mins < 0:
                logger.warning(f"Invalid mins value: {mins}")
                mins = max(0, int(mins)) if mins is not None else 0
                
            if not isinstance(total_seconds, (int, float)):
                logger.warning(f"Invalid total_seconds value: {total_seconds}")
                total_seconds = 0.0
                
            if not isinstance(is_today, bool):
                logger.warning(f"Invalid is_today value: {is_today}")
                is_today = False

            self.days = days
            self.hours = hours
            self.mins = mins
            self.total_seconds = float(total_seconds)
            self.is_today = is_today
            
            logger.debug(f"DateCountdown created: {days}d {hours}h {mins}m (today: {is_today})")
            
        except Exception as e:
            logger.error(f"Error creating DateCountdown: {e}", exc_info=True)
            # Fallback to safe defaults
            self.days = 0
            self.hours = 0
            self.mins = 0
            self.total_seconds = 0.0
            self.is_today = False

def _get_delta(target_month: int, target_day: int):
    """Calculate time delta to target date with error handling"""
    try:
        # Validate input parameters
        if not isinstance(target_month, int) or not (1 <= target_month <= 12):
            logger.error(f"Invalid target_month: {target_month}")
            raise ValueError(f"target_month must be between 1 and 12, got {target_month}")
            
        if not isinstance(target_day, int) or not (1 <= target_day <= 31):
            logger.error(f"Invalid target_day: {target_day}")
            raise ValueError(f"target_day must be between 1 and 31, got {target_day}")

        today = datetime.today()
        logger.debug(f"Calculating delta from {today.date()} to {target_month:02d}-{target_day:02d}")
        
        try:
            target_date = datetime(year=today.year, month=target_month, day=target_day)
        except ValueError as e:
            logger.error(f"Invalid date combination: month={target_month}, day={target_day}")
            raise ValueError(f"Invalid date: {target_month:02d}-{target_day:02d}")
            
        delta = target_date - today
        
        # If the date has passed this year, use next year
        if delta.days < -1:
            try:
                target_date = datetime(year=today.year + 1, month=target_month, day=target_day)
                delta = target_date - today
                logger.debug(f"Date has passed this year, using next year: {target_date.date()}")
            except ValueError as e:
                logger.error(f"Invalid date for next year: {target_month:02d}-{target_day:02d}")
                raise ValueError(f"Invalid date for next year: {target_month:02d}-{target_day:02d}")
        
        logger.debug(f"Delta calculated: {delta.days} days, {delta.seconds} seconds")
        return (delta, target_date)
        
    except Exception as e:
        logger.error(f"Error calculating delta for {target_month:02d}-{target_day:02d}: {e}")
        raise

def get_next_occurance(target_month: int, target_day: int) -> Optional[DateCountdown]:
    """Get countdown to next occurrence of a specific date"""
    try:
        if target_month is None or target_day is None:
            logger.error("target_month and target_day cannot be None")
            return None
            
        logger.info(f"Getting next occurrence for {target_month:02d}-{target_day:02d}")
        
        delta, target_date = _get_delta(target_month, target_day)
        
        # Calculate countdown components
        days = delta.days
        hours = int(delta.seconds // (60 * 60))
        mins = int((delta.seconds // 60) % 60)
        total_seconds = delta.total_seconds()
        is_today = datetime.now().date() == target_date.date()
        
        countdown = DateCountdown(
            days=days,
            hours=hours,
            mins=mins,
            total_seconds=total_seconds,
            is_today=is_today
        )
        
        logger.info(f"Next occurrence for {target_month:02d}-{target_day:02d}: {days} days, {hours} hours, {mins} minutes")
        return countdown
        
    except ValueError as e:
        logger.error(f"Invalid date parameters: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting next occurrence for {target_month:02d}-{target_day:02d}: {e}", exc_info=True)
        return None