/****** Object:  View [dbo].[PlusOneGLM]    Script Date: 2026-05-11 8:53:12 PM ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO


create view [dbo].[PlusOneGLM] as

select rtrim(i.ACTNUMST) 'GLAccountCode' ,rtrim(g.ACTNUMBR_1) 'CodeGroup',rtrim(g.ACTNUMBR_2) 'CodeNumber',rtrim(g.ACTDESCR) 'CodeDescription',
case ACTIVE when 0 then 'Inactive' when 1 then 'Active' else 'Unknown' end as 'CodeStatus' 
from GL00100 g 
join GL00105 i on i.ACTINDX = g.ACTINDX 
where ACTIVE = 1 
GO


