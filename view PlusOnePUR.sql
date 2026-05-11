
/****** Object:  View [dbo].[PlusOnePUR]    Script Date: 2026-05-11 8:53:25 PM ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO



CREATE   view [dbo].[PlusOnePUR] as

select 'GAP' 'PayerID',rtrim(ph.VENDORID) 'SupplierID',
cast(datepart(year,ph.DOCDATE) as char(4))+'-'+case when month(ph.DOCDATE)<10 then '0' else '' end+
	rtrim(cast(datepart(month,ph.DOCDATE) as char(2)))+'-'+case when day(ph.DOCDATE)<10 then '0' else '' end+
	rtrim(cast(datepart(day,ph.DOCDATE) as char(2))) 'DocumentDate',rtrim(ph.PONUMBER) 'PONumber','' 'HeaderRefNo',
			rtrim(USER2ENT) 'BuyerContact','' 'BuyerEmail' ,'Y' 'BuyerApproverPrev','' 'BuyerApproverNext',
			cast(pd.LineNumber as char(20)) 'LineNo',case when pd.POLNESTA in (4,5,6) then 'X' else '' end as 'LineRefNo1','Standard' 'LineRefNo2',rtrim(pd.ITEMNMBR) 'BuyerProductCode',
			rtrim(replace(pd.ITEMDESC,'"','')) 'ProductDescription',
			cast(pd.QTYORDER-pd.QTYCANCE as char(20)) 'OrderedQty',rtrim(pd.UOFM) 'OrderedQtyUOM',cast(pd.ORUNTCST as char(20)) 'NetPrice','1.00000' 'PerQty',
			cast(isnull(pq.QTYSHPPD,0) as char(20)) 'ReceivedQty', cast(isnull(pq.QTYINVCD,0) as char(20)) 'CostedQty', '' 'ReceivedValue', '' 'CostedValue',cast(pd.OREXTCST as char(20)) 'LineValueExclGST', 
			case when pd.ORTAXAMT > 0 then cast(cast(pd.ORTAXAMT/pd.OREXTCST as numeric(18,2)) as char(20)) else '0' end 'LineGSTRate',
			cast(pd.ORTAXAMT as char(20)) 'LineGSTValue',rtrim(ph.CURNCYID) 'Currency',pd.ORD

from POP10100 ph
join POP10110 pd on ph.PONUMBER=pd.PONUMBER
left join gurPOQtySummary pq on pd.PONUMBER=pq.PONUMBER and pd.ORD=pq.POLNENUM 
--left join hmlUserMaintenance um on ph.USER2ENT=um.[User ID]
where ph.POTYPE<>0 
GO


