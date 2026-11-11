select *
from {{ ref('quarantine_nav_daily') }}
where quarantine_reason is null
   or trim(quarantine_reason) = ''
