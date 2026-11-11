select *
from {{ ref('fact_nav_daily') }}
where {{ is_material_negative('nav') }}
   or {{ is_material_negative('aum') }}
   or {{ is_material_negative('holders') }}
