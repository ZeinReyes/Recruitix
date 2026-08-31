"""
standardize_title.py

RECRUITIX
PhilJobNet Job Title Standardization

Purpose
-------
Standardizes raw PhilJobNet job titles into broader career categories
while ALWAYS preserving the original job title.

Matching strategy
-----------------
1. Normalize the title.
2. Apply exact regex matching against CAREER_TAXONOMY.
3. Apply conservative fuzzy matching as a fallback.
4. If no reliable match exists, return "Uncategorized".

Important
---------
Do NOT remove "associate" from titles.

For example:

    SALES ASSOCIATE PROFESSIONAL

must remain:

    sales associate professional

because "associate" is part of the actual job title.

The taxonomy is intentionally ordered from specific to broad.
"""


import re

from rapidfuzz import fuzz, process


# ============================================================
# CONFIGURATION
# ============================================================

# Higher = safer but more Uncategorized.
# Lower = more coverage but greater risk of false matches.
SCORE_CUTOFF = 84


# ============================================================
# CAREER TAXONOMY
# ============================================================
#
# IMPORTANT:
# More specific categories must appear BEFORE broad categories.
#
# Example:
#
#   "SITE ENGINEER"
#
# should become:
#
#   Construction
#
# rather than:
#
#   Engineering
#
# because Construction is checked first.
#
# ============================================================

CAREER_TAXONOMY = [

    # ========================================================
    # DATA / ANALYTICS
    # ========================================================

    (
        "Data Analyst",
        [
            r"\bdata\s+analyst\b",
            r"\bdata\s+analytics\b",
            r"\bdata\s+analysis\b",
            r"\banalyst\s*[/\-]\s*data\b",
            r"\bdata\s+reporting\b",
        ],
    ),

    (
        "Data Scientist",
        [
            r"\bdata\s+scientist\b",
            r"\bdata\s+science\b",
        ],
    ),

    (
        "BI Analyst",
        [
            r"\bbi\s+analyst\b",
            r"\bbusiness\s+intelligence\s+analyst\b",
            r"\bbusiness\s+intelligence\b",
            r"\bbi\s+developer\b",
        ],
    ),

    (
        "Analytics Engineer",
        [
            r"\banalytics\s+engineer\b",
        ],
    ),

    (
        "Business Analyst",
        [
            r"\bbusiness\s+analyst\b",
            r"\bbusiness\s+systems\s+analyst\b",
            r"\bsystems\s+analyst\b",
            r"\bmanagement\s+analyst\b",
            r"\boperations\s+analyst\b",
            r"\bquality\s+analyst\b",
        ],
    ),

    # ========================================================
    # SOFTWARE / IT
    # ========================================================

    (
        "Full Stack Developer",
        [
            r"\bfull\s*[-/]?\s*stack\s+developer\b",
            r"\bfull\s*[-/]?\s*stack\s+engineer\b",
            r"\bfullstack\s+developer\b",
            r"\bfullstack\s+engineer\b",
        ],
    ),

    (
        "Backend Developer",
        [
            r"\bbackend\s+developer\b",
            r"\bback[-\s]?end\s+developer\b",
            r"\bbackend\s+engineer\b",
            r"\bback[-\s]?end\s+engineer\b",
            r"\bbackend\s+programmer\b",
            r"\bback[-\s]?end\s+programmer\b",
        ],
    ),

    (
        "Frontend Developer",
        [
            r"\bfrontend\s+developer\b",
            r"\bfront[-\s]?end\s+developer\b",
            r"\bfrontend\s+engineer\b",
            r"\bfront[-\s]?end\s+engineer\b",
        ],
    ),

    (
        "Software Engineer",
        [
            r"\bsoftware\s+engineer\b",
            r"\bsoftware\s+developer\b",
            r"\bsoftware\s+programmer\b",
            r"\bapplication\s+developer\b",
            r"\bapplication\s+engineer\b",
            r"\bcomputer\s+programmer\b",
            r"\bjava\s+programmer\b",
            r"\bprogrammer\b",
        ],
    ),

    (
        "Web Developer",
        [
            r"\bweb\s+developer\b",
            r"\bweb\s+programmer\b",
            r"\bweb\s+designer\b",
        ],
    ),

    (
        "DevOps / Cloud",
        [
            r"\bdevops\b",
            r"\bdevops\s+engineer\b",
            r"\bcloud\s+engineer\b",
            r"\bcloud\s+administrator\b",
            r"\bcloud\s+architect\b",
            r"\bsite\s+reliability\s+engineer\b",
            r"\bsre\b",
        ],
    ),

    (
        "Database",
        [
            r"\bdatabase\s+administrator\b",
            r"\bdatabase\s+developer\b",
            r"\bdatabase\s+engineer\b",
            r"\bdba\b",
        ],
    ),

    (
        "Systems / IT",
        [
            r"\binformation\s+technology\b",
            r"\binformation\s+systems?\b",
            r"\binformation\s+technology\s+officer\b",
            r"\binformation\s+technology\s+consultant\b",
            r"\bmanagement\s+information\s+system\b",
            r"\bcomputer\s+operator\b",
            r"\bcomputer\s+systems?\b",
            r"\bsystems?\s+developer\b",
            r"\bsystems?\s+analyst\b",
            r"\binformation\s+officer\b",
        ],
    ),

    (
        "Network Engineer",
        [
            r"\bnetwork\s+engineer\b",
            r"\bnetwork\s+administrator\b",
            r"\bnetwork\s+technician\b",
            r"\bnetwork\s+specialist\b",
            r"\bnetwork\s+officer\b",
        ],
    ),

    (
        "Cybersecurity",
        [
            r"\bcybersecurity\b",
            r"\bcyber\s+security\b",
            r"\binformation\s+security\b",
            r"\bsecurity\s+analyst\b",
            r"\bsecurity\s+engineer\b",
            r"\bsoc\s+analyst\b",
            r"\bsecurity\s+officer\b",
            r"\bsecurity\s+guard\b",
            r"\bwatchman\b",
        ],
    ),

    (
        "IT Support",
        [
            r"\bit\s+support\b",
            r"\btechnical\s+support\b",
            r"\btechnical\s+service\b",
            r"\btechnical\s+assistant\b",
            r"\bhelp\s*desk\b",
            r"\bit\s+technician\b",
            r"\bit\s+specialist\b",
            r"\bit\s+administrator\b",
            r"\bsystem\s+administrator\b",
        ],
    ),

    # ========================================================
    # QA / QUALITY
    # ========================================================

    (
        "QA / Tester",
        [
            r"\bqa\s+engineer\b",
            r"\bqa\s+analyst\b",
            r"\bqa\s+tester\b",
            r"\bquality\s+assurance\b",
            r"\btest\s+engineer\b",
            r"\bsoftware\s+tester\b",
            r"\btester\b",
            r"\bquality\s+control\b",
            r"\bquality\s+assurance\b",
            r"\bquality\s+inspector\b",
            r"\bquality\s+control\s+officer\b",
            r"\bquality\s+control\s+assistant\b",
            r"\bquality\s+control\s+chemist\b",
        ],
    ),

    # ========================================================
    # ACCOUNTING / FINANCE / AUDIT
    # ========================================================

    (
        "Accountant",
        [
            r"\baccountant\b",
            r"\baccounting\s+specialist\b",
            r"\baccounting\s+officer\b",
            r"\baccounting\s+assistant\b",
            r"\baccounting\s+staff\b",
            r"\baccounting\s+clerk\b",
            r"\baccounting\s+analyst\b",
            r"\bbookkeeper\b",
            r"\bbookkeeping\b",
            r"\baccounts?\s+coordinator\b",
            r"\baccounts?\s+executive\b",
            r"\baccounts?\s+assistant\b",
            r"\baccounts?\s+clerk\b",
        ],
    ),

    (
        "Audit",
        [
            r"\binternal\s+auditor\b",
            r"\bexternal\s+auditor\b",
            r"\bauditor\b",
            r"\bauditing\b",
            r"\baudit\s+assistant\b",
            r"\baudit\s+analyst\b",
            r"\bhead\s+internal\s+audit\b",
            r"\btechnical\s+audit\b",
        ],
    ),

    (
        "Finance",
        [
            r"\bfinancial\s+analyst\b",
            r"\bfinancial\s+planner\b",
            r"\bfinance\s+specialist\b",
            r"\bfinance\s+officer\b",
            r"\bfinancial\s+consultant\b",
            r"\bcredit\s+officer\b",
            r"\bcredit\s+analyst\b",
            r"\bcredit\s+investigator\b",
            r"\bcredit\s+and\s+collection\b",
            r"\bcollection\s+officer\b",
            r"\bcollection\s+assistant\b",
            r"\bcredit\s*[/\-]\s*collection\b",
            r"\bdebt\s+collector\b",
            r"\bbank\s+teller\b",
            r"\bteller\b",
            r"\bbilling\s+officer\b",
            r"\bbilling\s+clerk\b",
            r"\binvoicing\s+clerk\b",
            r"\btreasury\b",
            r"\btreasury\s+assistant\b",
            r"\bloans?\s+assistant\b",
            r"\binsurance\s+adviser\b",
            r"\binsurance\s+advisor\b",
            r"\binsurance\s+agent\b",
            r"\binsurance\b",
            r"\bunderwriting\b",
            r"\bclaims\b",
            r"\bfinancial\s*[/\-]\s*accounts?\b",
            r"\bfinancial\s+accounts?\s+specialist\b",
            r"\bfinance\b",
        ],
    ),

    # ========================================================
    # BUSINESS
    # ========================================================

    (
        "Business Development",
        [
            r"\bbusiness\s+development\b",
            r"\bproject\s+development\b",
            r"\bproperty\s+development\b",
        ],
    ),

    (
        "Procurement",
        [
            r"\bpurchasing\s+clerk\b",
            r"\bpurchasing\s+officer\b",
            r"\bpurchasing\b",
            r"\bprocurement\b",
            r"\bpurchaser\b",
            r"\bbuyer\b",
            r"\bmerchandise\s+buyer\b",
            r"\border\s*[/&]?\s*materials\s+clerk\b",
        ],
    ),

    (
        "HR Specialist",
        [
            r"\bhr\s+specialist\b",
            r"\bhr\s+officer\b",
            r"\bhr\s+associate\b",
            r"\bhuman\s+resources?\b",
            r"\bpersonnel\s+clerk\b",
            r"\brecruiter\b",
            r"\brecruitment\s+specialist\b",
            r"\brecruitment\s+officer\b",
            r"\blabor\s+relations\b",
            r"\blabor\s+relations\s+officer\b",
        ],
    ),

    (
        "Training & Development",
        [
            r"\btraining\s+officer\b",
            r"\btraining\s+coordinator\b",
            r"\btraining\s+specialist\b",
            r"\binstructor\b",
            r"\bfacilitator\b",
            r"\bteacher\s+assistant\b",
        ],
    ),

    # ========================================================
    # MARKETING / SALES
    # ========================================================

    (
        "Marketing Specialist",
        [
            r"\bmarketing\s+specialist\b",
            r"\bmarketing\s+assistant\b",
            r"\bmarketing\s+officer\b",
            r"\bdigital\s+marketing\b",
            r"\bmarketing\s+coordinator\b",
            r"\badvertising\s+officer\b",
            r"\bmarketing\b",
        ],
    ),

    (
        "Sales Manager",
        [
            r"\bsales\s+manager\b",
            r"\bsales\s+supervisor\b",
            r"\bsales\s+director\b",
            r"\bsales\s+head\b",
            r"\bsales\s+leader\b",
        ],
    ),

    (
        "Sales Representative",
        [
            # Main Sales titles
            r"\bsales\s+representative\b",
            r"\bsales\s+associate\b",
            r"\bsales\s+associate\s+professional\b",
            r"\bsales\s+agent\b",
            r"\bsalesperson\b",
            r"\bsalesman\b",
            r"\bsaleswoman\b",
            r"\bsaleslady\b",
            r"\bsales\s+executive\b",
            r"\bsales\s+clerk\b",
            r"\bsales\s+officer\b",
            r"\bsales\s+coordinator\b",
            r"\bsales\s+staff\b",
            r"\bsales\s+personnel\b",
            r"\bsales\s+specialist\b",
            r"\bsales\s+consultant\b",
            r"\bsales\s+promoter\b",
            r"\bsales\s+assistant\b",
            r"\bfield\s+sales\b",
            r"\boutside\s+sales\b",
            r"\binside\s+sales\b",
            r"\bsales\s+advisor\b",
            r"\bsales\s+adviser\b",
            r"\btelemarketer\b",
            r"\bcanvasser\b",

            # Sales / Marketing combinations
            r"\bsales\s+and\s+marketing\b",
            r"\bsales\s*/\s*marketing\b",
            r"\bsales\s*[-&]\s*marketing\b",

            # Product / property sales
            r"\bproduct\s+specialist\b",
            r"\bbeauty\s+consultant\b",
            r"\bproperty\s+consultant\b",
        ],
    ),

    # ========================================================
    # CUSTOMER SERVICE
    # ========================================================

    (
        "Customer Service",
        [
            r"\bcustomer\s+service\b",
            r"\bcustomer\s+support\b",
            r"\bcustomer\s+care\b",
            r"\bcustomer\s+relations?\s+officer\b",
            r"\bcsr\b",
            r"\bcall\s+cent(?:er|re)\b",
            r"\btechnical\s+service\s+adviser\b",
            r"\bservice\s+adviser\b",
            r"\bservice\s+advisor\b",
        ],
    ),

    # ========================================================
    # RETAIL / MERCHANDISING
    # ========================================================

    (
        "Retail",
        [
            r"\bstore\s+manager\b",
            r"\bstore\s+supervisor\b",
            r"\bassistant\s+store\s+manager\b",
            r"\bretail\b",
            r"\bstockman\b",
            r"\bstock\s+clerk\b",
            r"\bcashier\b",
            r"\bretail\s+associate\b",
            r"\bflorist\b",
            r"\bcart\s+pusher\b",
            r"\bcounter\s+clerk\b",
            r"\bticket\s+clerk\b",
            r"\bmerchandiser\b",
            r"\bmerchandising\b",
            r"\bmerchandising\s+assistant\b",
            r"\bmerchandising\s+officer\b",
            r"\bbuyer\s*,?\s*merchandise\b",
        ],
    ),

    # ========================================================
    # LOGISTICS / TRANSPORT
    # ========================================================

    (
        "Logistics",
        [
            r"\blogistics\b",
            r"\bwarehouse\b",
            r"\binventory\s+clerk\b",
            r"\binventory\s+control\b",
            r"\bstoreroom\s+clerk\b",
            r"\breceiving\s+clerk\b",
            r"\bshipping\b",
            r"\bdelivery\b",
            r"\bdispatcher\b",
            r"\bsupply\s+chain\b",
            r"\bcompany\s+driver\b",
            r"\btruck\s+driver\b",
            r"\btrailer\s+driver\b",
            r"\bmotorcycle\s+driver\b",
            r"\brider\b",
            r"\bforklift\s+operator\b",
            r"\bdriver\b",
            r"\bmessenger\b",
            r"\bcourier\b",
            r"\bfreight\b",
            r"\bdispatching\b",
            r"\bmaterials?\s+clerk\b",
            r"\btruck\s+helper\b",
            r"\bbus\s+conductor\b",
            r"\bbus\s+driver\b",
        ],
    ),

    # ========================================================
    # ENGINEERING
    # ========================================================

    (
        "Construction",
        [
            r"\bconstruction\b",
            r"\bsite\s+engineer\b",
            r"\bsite\s+supervisor\b",
            r"\bconstruction\s+engineer\b",
            r"\bforeman\b",
            r"\bcarpenter\b",
            r"\bmason\b",
            r"\bscaffolder\b",
            r"\bhousebuilder\b",
            r"\bsteel\s+erector\b",
            r"\bconstructional\s+steel\s+erector\b",
            r"\bbuilding\s+administrator\b",
            r"\bplasterer\b",
            r"\baluminum\s+installer\b",
            r"\bhouse\s+builder\b",
        ],
    ),

    (
        "Architecture & Design",
        [
            r"\barchitect\b",
            r"\barchitectural\s+designer\b",
            r"\barchitectural\s+draftsman\b",
            r"\bdraftsman\b",
            r"\bdrafter\b",
            r"\bautocad\s+operator\b",
            r"\bcomputer\s+aided\s+design\b",
            r"\bcomputer\s+aided\s+drafting\b",
            r"\bcad\s+operator\b",
            r"\binterior\s+designer\b",
            r"\bgraphic\s+designer\b",
            r"\bgraphic\s+artist\b",
            r"\bart\s+director\b",
            r"\bfashion\s+designer\b",
            r"\bindustrial\s+and\s+commercial\s+products\s+designer\b",
        ],
    ),

    (
        "Civil Engineering",
        [
            r"\bcivil\s+engineer\b",
            r"\bland\s+surveyor\b",
            r"\bquantity\s+surveyor\b",
        ],
    ),

    (
        "Mechanical Engineering",
        [
            r"\bmechanical\s+engineer\b",
            r"\bmechanical\s+engineering\b",
        ],
    ),

    (
        "Electrical Engineering",
        [
            r"\belectrical\s+engineer\b",
            r"\belectrical\s+inspector\b",
            r"\belectrical\s+engineering\b",
            r"\belectric\s+power\s+lineman\b",
        ],
    ),

    (
        "Electronics Engineering",
        [
            r"\belectronics\s+engineer\b",
            r"\belectronics\s+engineering\b",
        ],
    ),

    (
        "Industrial Engineering",
        [
            r"\bindustrial\s+engineer\b",
            r"\bindustrial\s+engineering\b",
        ],
    ),

    (
        "Engineering",
        [
            r"\bchemical\s+engineer\b",
            r"\bengineer\b",
            r"\bengineering\b",
        ],
    ),

    # ========================================================
    # SKILLED TRADES / TECHNICAL
    # ========================================================

    (
        "Skilled Trades",
        [
            r"\btechnician\b",
            r"\belectrician\b",
            r"\belectrical\s+helper\b",
            r"\bmechanical\s+helper\b",
            r"\bplumber\b",
            r"\bwelding\b",
            r"\bwelder\b",
            r"\btailor\b",
            r"\bmaintenance\b",
            r"\bmechanic\b",
            r"\bmachinist\b",
            r"\bmetal\s+fabricator\b",
            r"\bmetal\s+fabrication\b",
            r"\btinsmith\b",
            r"\bpipe\s+fitter\b",
            r"\bsteelman\b",
            r"\biron\s+works\s+fabricator\b",
            r"\bshoes?\s+and\s+bags?\s+repairer\b",
            r"\bvehicle\s+washer\b",
            r"\bcarwash\s+attendant\b",
            r"\bpaint(?:er|ing)\b",
            r"\bautomotive\s+painter\b",
            r"\baircraft\s+painter\b",
            r"\bship\s+painter\b",
        ],
    ),

    # ========================================================
    # PRODUCTION / MANUFACTURING
    # ========================================================

    (
        "Manufacturing / Production",
        [
            r"\bproduction\s+machine\s+operator\b",
            r"\bproduction\s+worker\b",
            r"\bproduction\s+helper\b",
            r"\bproduction\s+planner\b",
            r"\bproduction\s+assistant\b",
            r"\bproduction\s+and\s+operations\b",
            r"\bmanufacturing\b",
            r"\bmanufacturing\s+laborer\b",
            r"\bmachine\s+operator\b",
            r"\bmachine\s+tool\s+machine\s+operator\b",
            r"\bmachine\s+tool\b",
            r"\bbread\s+production\s+machine\s+operator\b",
            r"\bplastic\s+production\s+machine\s+operator\b",
            r"\bcutting\s+product\s+machine\s+operator\b",
            r"\bfurniture\s+production\s+machine\s+operator\b",
            r"\bbraid\s+production\s+machine\s+operator\b",
            r"\boffset\s+machine\s+operator\b",
            r"\brolling\s+mill\b",
            r"\bmill\s+operator\b",
            r"\bextruding\s+machine\s+operator\b",
            r"\bmelting\s+metal\s+furnace\s+operator\b",
            r"\bboiler\s+fireman\b",
            r"\bheavy\s+equipment\s+operator\b",
            r"\bcrane\s+operator\b",
            r"\bpayloader\s+operator\b",
            r"\bbridge\s+or\s+gantry\s+crane\s+operator\b",
            r"\bstationary\s+jib\s+crane\s+operator\b",
            r"\bbackhoe\s+excavator\s+operator\b",
            r"\bhydraull?ic\s+backhoe\s+excavator\s+operator\b",
            r"\bmetal\s+fabricator\b",
            r"\btextile\s+cutter\b",
            r"\bassembly[-\s]?line\s+worker\b",
            r"\bwood\s+pattern\s+maker\b",
        ],
    ),

    # ========================================================
    # HEALTHCARE
    # ========================================================

    (
        "Healthcare",
        [
            r"\bnurse\b",
            r"\bnursing\s+aide\b",
            r"\bdoctor\b",
            r"\bphysician\b",
            r"\bmedical\b",
            r"\bhealthcare\b",
            r"\bdentist\b",
            r"\bdental\s+assistant\b",
            r"\bpharmacist\b",
            r"\bcaregiver\b",
            r"\bmedical\s+technologist\b",
            r"\bradiologic\s+technologist\b",
            r"\bphysical\s+therapist\b",
            r"\bphysiotherapist\b",
            r"\bphysiotherapist\b",
            r"\bspeech\s+therapist\b",
            r"\bmidwife\b",
            r"\bhospital\s+attendant\b",
            r"\bpsychometrician\b",
            r"\bmasseur\b",
        ],
    ),

    # ========================================================
    # FOOD / HOSPITALITY
    # ========================================================

    (
        "Food & Hospitality",
        [
            r"\brestaurant\b",
            r"\bkitchen\b",
            r"\bcook\b",
            r"\bchef\b",
            r"\bwaiter\b",
            r"\bwaitress\b",
            r"\bhotel\b",
            r"\bhospitality\b",
            r"\bbarista\b",
            r"\bbartender\b",
            r"\bservice\s+crew\b",
            r"\bfood\s+attendant\b",
            r"\bfood\s+server\b",
            r"\bdishwasher\b",
            r"\bbaker\b",
            r"\bbread\s+baker\b",
            r"\bcommis\s+helper\b",
            r"\bbusboy\b",
            r"\bbanquet\s+coordinator\b",
            r"\bsteward\b",
            r"\bship\s+steward\b",
            r"\bbutler\b",
            r"\bhousekeeper\b",
            r"\bhousekeeping\b",
            r"\bporter\b",
            r"\bvalet\b",
            r"\bbuilding\s+concierge\b",
            r"\busher\b",
            r"\breservation\s+officer\b",
            r"\breservation\s+clerk\b",
        ],
    ),

    # ========================================================
    # ADMINISTRATIVE
    # ========================================================

    (
        "Administrative",
        [
            r"\badministrative\b",
            r"\badministration\b",
            r"\badmin\s+assistant\b",
            r"\bsecretary\b",
            r"\bexecutive\s+assistant\b",
            r"\boffice\s+assistant\b",
            r"\boffice\s+clerk\b",
            r"\breceptionist\b",
            r"\bclerical\b",
            r"\bdata\s+encoder\b",
            r"\bdata\s+entry\s+clerk\b",
            r"\bdocumentation\s+staff\b",
            r"\bdocumentation\s+clerk\b",
            r"\bproject\s+assistant\b",
            r"\bproject\s+coordinator\b",
            r"\bproject\s+officer\b",
            r"\bproject\s+management\s+officer\b",
            r"\bliaison\s+officer\b",
            r"\bliaison\s+assistant\b",
            r"\bclerk[-\s]processor\b",
            r"\btimekeeper\b",
            r"\bweighing\s+clerk\b",
            r"\bpayroll\s+clerk\b",
            r"\bpayroll\s+master\b",
            r"\bexport\s*[/\-]\s*import\s+officer\b",
            r"\bexport\s*[/\-]\s*import\s+coordinator\b",
            r"\bexport\s*[/\-]\s*import\b",
        ],
    ),

    # ========================================================
    # AGRICULTURE
    # ========================================================

    (
        "Agriculture",
        [
            r"\bfarm\b",
            r"\bfarm\s+manager\b",
            r"\bfarm\s+worker\b",
            r"\bfarmer\b",
            r"\boverseer\b",
            r"\bagricultur\w*\b",
            r"\bplantation\b",
            r"\bcacao\s+farmer\b",
            r"\bvegetable\s+farmer\b",
            r"\bforestry\s+laborer\b",
            r"\bfishery\b",
        ],
    ),

    # ========================================================
    # MARITIME
    # ========================================================

    (
        "Maritime",
        [
            r"\bship\s+crew\b",
            r"\bseafarer\b",
            r"\bseaman\b",
            r"\bdeckhand\b",
            r"\bmarine\b",
            r"\bthird\s+mate\b",
            r"\bsecond\s+mate\b",
            r"\bchief\s+mate\b",
            r"\bship\s+master\b",
            r"\bship\s+steward\b",
            r"\bmotorman\b",
            r"\brigger\b",
            r"\bscuba\s+diver\b",
        ],
    ),

    # ========================================================
    # GENERAL LABOR
    # ========================================================

    (
        "General Labor",
        [
            r"\blaborer\b",
            r"\blabor\s+worker\b",
            r"\bhelper\b",
            r"\bproduction\s+helper\b",
            r"\butility\s+worker\b",
            r"\bjanitor\b",
            r"\bbutcher\b",
            r"\bfood\s+repacker\b",
            r"\bgardener\b",
            r"\bgarden\s+helper\b",
            r"\bparking\s+attendant\b",
            r"\bfuel\s*/?\s*gas\s+attendant\b",
            r"\bgasoline\s+pump\s+boy\b",
            r"\bwater\s+meter\s+reader\b",
            r"\bvehicle\s+washer\b",
            r"\bcar\s*wash\s+attendant\b",
            r"\butilityman\b",
        ],
    ),

    # ========================================================
    # DOMESTIC WORK
    # ========================================================

    (
        "Domestic Work",
        [
            r"\bdomestic\s+helper\b",
            r"\bdomestic\s+cleaner\b",
            r"\bhousehold\s+attendant\b",
            r"\bkasambahay\b",
            r"\bhousemaid\b",
            r"\bbabysitter\b",
            r"\bbaby\s+sitter\b",
            r"\bhousekeeper\s*\(\s*private\s*\)",
            r"\blaundry\s+worker\b",
            r"\blaundry\b",
            r"\bdry\s+cleaner\b",
            r"\bwashing\s*[/\-]?\s*laundry\b",
        ],
    ),

    # ========================================================
    # EDUCATION
    # ========================================================

    (
        "Education",
        [
            r"\bteacher\b",
            r"\binstructor\b",
            r"\btutor\b",
            r"\bsecondary\s+education\b",
            r"\belementary\s+science\b",
            r"\btechnical\s+and\s+vocational\b",
            r"\bspecial\s+education\b",
            r"\btertiary\s+education\b",
            r"\bsocial\s+sciences?\s+teacher\b",
            r"\bgeneral\s+nursing\s+teacher\b",
            r"\bschool\s+librarian\b",
        ],
    ),

    # ========================================================
    # LEGAL
    # ========================================================

    (
        "Legal",
        [
            r"\blawyer\b",
            r"\blegal\s+assistant\b",
            r"\blegal\b",
        ],
    ),

    # ========================================================
    # SCIENCE / ENVIRONMENT
    # ========================================================

    (
        "Science & Research",
        [
            r"\blaboratory\s+analyst\b",
            r"\blaboratory\s+assistant\b",
            r"\blaboratory\s+aide\b",
            r"\bchemist\b",
            r"\bbiologist\b",
            r"\bfood\s+technologist\b",
            r"\bfood\s+technology\b",
            r"\benvironmental\s+specialist\b",
            r"\benvironmental\s+analyst\b",
            r"\benvironmental\b",
        ],
    ),

    # ========================================================
    # COMMUNICATION / MEDIA / CREATIVE
    # ========================================================

    (
        "Creative & Media",
        [
            r"\bgraphic\s+artist\b",
            r"\bgraphic\s+designer\b",
            r"\bcreative\s+writer\b",
            r"\bwriter\b",
            r"\beditor\b",
            r"\bcommunication\s+consultant\b",
            r"\bcommunication\s+specialist\b",
            r"\bcommunity\s+relations\b",
            r"\bcommunity\s+relations\s+officer\b",
            r"\bprofessional\s+dancer\b",
            r"\bpropsman\b",
            r"\bpainting\s+restorer\b",
        ],
    ),

    # ========================================================
    # SAFETY / COMPLIANCE
    # ========================================================

    (
        "Safety & Compliance",
        [
            r"\bsafety\s+officer\b",
            r"\bsafety\s+specialist\b",
            r"\bcompliance\s+officer\b",
            r"\bcompliance\b",
        ],
    ),

    # ========================================================
    # MANAGEMENT
    # ========================================================
    #
    # Keep broad management LAST.
    #

    (
        "Management",
        [
            r"\bbranch\s+manager\b",
            r"\bbranch\s+head\b",
            r"\bgeneral\s+manager\b",
            r"\boperations\s+manager\b",
            r"\boperations\s+supervisor\b",
            r"\bdepartment\s+manager\b",
            r"\bcorporate\s+director\b",
            r"\bmanaging\s+director\b",
            r"\bchief\s+executive\s+officer\b",
            r"\bassistant\s+vice\s+president\b",
            r"\bcluster\s+head\b",
            r"\bmanagement\s+specialist\b",
            r"\bmanagement\b",
            r"\bmanager\b",
            r"\bsupervisor\b",
            r"\bhead\b",
        ],
    ),
]


# ============================================================
# FUZZY MATCHING PREPARATION
# ============================================================

def _pattern_to_phrase(pattern: str) -> str:
    """
    Convert a regex pattern into a rough human-readable phrase
    for fuzzy matching.
    """

    phrase = pattern

    phrase = phrase.replace(r"\b", "")
    phrase = phrase.replace(r"\w*", "")
    phrase = phrase.replace(r"\w+", "")
    phrase = phrase.replace(r"\s+", " ")

    phrase = re.sub(
        r"[\[\]{}().,+*?^$|\\]",
        " ",
        phrase,
    )

    phrase = re.sub(
        r"\s+",
        " ",
        phrase,
    )

    return phrase.strip()


_FUZZY_CHOICES = []
_FUZZY_CATEGORY_BY_PHRASE = {}


for _category, _patterns in CAREER_TAXONOMY:

    for _pattern in _patterns:

        _phrase = _pattern_to_phrase(
            _pattern
        )

        if (
            _phrase
            and _phrase
            not in _FUZZY_CATEGORY_BY_PHRASE
        ):

            _FUZZY_CHOICES.append(
                _phrase
            )

            _FUZZY_CATEGORY_BY_PHRASE[
                _phrase
            ] = _category


# ============================================================
# TITLE CLEANING
# ============================================================

# IMPORTANT:
# "associate" is intentionally NOT included.
#
# Sales Associate
# Sales Associate Professional
# HR Associate
#
# all need "associate" for matching.

SENIORITY_NOISE = re.compile(
    r"""
    \b(
        jr\.?
        |
        junior
        |
        sr\.?
        |
        senior
        |
        lead
        |
        principal
        |
        entry[-\s]?level
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def clean_title_string(
    raw: str,
) -> str:
    """
    Normalize a raw job title.

    Examples:

        "SENIOR Sales Associate"
            -> "sales associate"

        "Sales & Marketing Staff"
            -> "sales and marketing staff"

        "QUALITY CONTROL/ASSURANCE OFFICER"
            -> "quality control assurance officer"
    """

    if not raw:
        return ""

    text = str(
        raw
    ).strip().lower()

    # Remove seniority modifiers.
    text = SENIORITY_NOISE.sub(
        " ",
        text,
    )

    # Normalize common symbols.
    text = text.replace(
        "&",
        " and ",
    )

    # Convert slashes to spaces.
    # This allows:
    #
    # CREDIT/COLLECTION
    # SALES/MARKETING
    #
    # to be matched naturally.
    text = text.replace(
        "/",
        " ",
    )

    # Convert hyphens to spaces.
    text = text.replace(
        "-",
        " ",
    )

    # Remove parentheses and punctuation.
    text = re.sub(
        r"[^a-z0-9 ]+",
        " ",
        text,
    )

    # Collapse whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# EXACT MATCH
# ============================================================

def _exact_match(
    cleaned: str,
) -> str | None:
    """
    Search the taxonomy in priority order.

    The first matching category wins.
    """

    if not cleaned:
        return None

    for category, patterns in CAREER_TAXONOMY:

        for pattern in patterns:

            if re.search(
                pattern,
                cleaned,
                re.IGNORECASE,
            ):

                return category

    return None


# ============================================================
# FUZZY MATCH
# ============================================================

def _fuzzy_match(
    cleaned: str,
) -> tuple[str, int] | None:
    """
    Conservative fuzzy fallback.

    Uses token-set and token-sort similarity.

    Fuzzy matching should NEVER be the main classifier.
    Exact taxonomy matches always take priority.
    """

    if not cleaned:
        return None

    # --------------------------------------------------------
    # Extract possible individual words/phrases.
    # --------------------------------------------------------

    result = process.extractOne(
        cleaned,
        _FUZZY_CHOICES,
        scorer=fuzz.token_set_ratio,
        score_cutoff=SCORE_CUTOFF,
    )

    if result is None:
        return None

    matched_phrase, score, _ = result

    category = (
        _FUZZY_CATEGORY_BY_PHRASE
        .get(matched_phrase)
    )

    if category is None:
        return None

    return (
        category,
        int(score),
    )


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def standardize_title(
    raw: str,
) -> dict:
    """
    Standardize a single job title.

    Returns:

        {
            "job_title": original title,
            "career_category": category,
            "match_method": "exact" / "fuzzy(score)" / None
        }
    """

    # --------------------------------------------------------
    # Missing title
    # --------------------------------------------------------

    if (
        raw is None
        or not str(raw).strip()
    ):

        return {
            "job_title": "",
            "career_category":
                "Uncategorized",
            "match_method": None,
        }

    # --------------------------------------------------------
    # Preserve original title exactly.
    # --------------------------------------------------------

    original_title = str(
        raw
    ).strip()

    # --------------------------------------------------------
    # Normalize only for matching.
    # --------------------------------------------------------

    cleaned = clean_title_string(
        original_title
    )

    # --------------------------------------------------------
    # Exact match
    # --------------------------------------------------------

    exact = _exact_match(
        cleaned
    )

    if exact:

        return {
            "job_title":
                original_title,

            "career_category":
                exact,

            "match_method":
                "exact",
        }

    # --------------------------------------------------------
    # Fuzzy fallback
    # --------------------------------------------------------

    fuzzy = _fuzzy_match(
        cleaned
    )

    if fuzzy:

        category, score = fuzzy

        return {
            "job_title":
                original_title,

            "career_category":
                category,

            "match_method":
                f"fuzzy({score})",
        }

    # --------------------------------------------------------
    # Uncategorized
    # --------------------------------------------------------

    return {
        "job_title":
            original_title,

        "career_category":
            "Uncategorized",

        "match_method":
            None,
    }


# ============================================================
# OPTIONAL TEST
# ============================================================
#
# Run:
#
#     python standardize_title.py
#
# to quickly test common PhilJobNet titles.
#
# ============================================================

if __name__ == "__main__":

    test_titles = [

        "SALES ASSOCIATE PROFESSIONAL",
        "SALESLADY",
        "INVENTORY CLERK",
        "DISHWASHER",
        "ACCOUNTS COORDINATOR",
        "GRAPHIC ARTIST",
        "CART PUSHER",
        "INTERNAL AUDITOR",
        "ACCOUNTING ANALYST",
        "INFORMATION TECHNOLOGY OFFICER",
        "BAKER (GENERAL)",
        "PRODUCTION MACHINE OPERATOR",
        "ACCOUNTS EXECUTIVE",
        "MACHINIST",
        "QUANTITY SURVEYOR",
        "FRONT DESK OFFICER",
        "GRAPHIC DESIGNER",
        "FOOD SERVER",
        "QUALITY CONTROL/ASSURANCE OFFICER",
        "DOCUMENTATION STAFF",
        "GARDENER",
        "PRODUCT SPECIALIST",
        "MERCHANDISING ASSISTANT",
        "TECHNICAL SERVICE ADVISER",
        "UTILITYMAN",
        "MESSENGER",
        "PAINTER",
        "HEAVY EQUIPMENT OPERATOR",
        "EXECUTIVE ASSISTANT",
        "FINANCIAL PLANNER",
        "FRONT DESK CLERK",
        "PROJECT COORDINATOR",
        "TREASURY ASSISTANT",
        "PHYSICAL THERAPIST",
        "RIGGER",
        "OPERATIONS OFFICER",
        "PARKING ATTENDANT",
        "AUTOCAD OPERATOR",
        "BEAUTY CONSULTANT",
        "RADIOLOGIC TECHNOLOGIST",
        "BARTENDER",
        "LABORATORY ANALYST",
        "PRODUCTION PLANNER",
        "METAL FABRICATOR",
        "TELEMARKETER",
        "CREDIT ANALYST",
        "COLLECTION ASSISTANT",
        "BABY SITTER",
        "HAIRDRESSER",
        "QUALITY ANALYST",
        "THIRD MATE",
        "PIPE FITTER",
        "SHIP MASTER",
        "DOMESTIC CLEANER",
        "TRAINING OFFICER",
        "HAIR STYLIST",
        "LABOR RELATIONS OFFICER",
        "DATA ENTRY CLERK (COMPUTER)",
        "PROJECT ASSISTANT",
        "PROMO GIRL",
        "FIELD INTERVIEWER",
        "CREDIT AND COLLECTION CLERK",
        "STOREROOM CLERK",
        "ARCHITECTURAL DRAFTSMAN",
        "COMPUTER OPERATOR",
        "PURCHASER",
        "QUALITY INSPECTOR",
        "STORE HELPER",
        "PROPERTY CONSULTANT",
        "CREDIT INVESTIGATOR",
        "PROFESSIONAL TUTOR",
        "LIFEGUARD",
        "ARCHITECT",
        "CASH COLLECTOR",
        "SECURITY OFFICER",
        "HOSPITAL ATTENDANT",
        "OPERATIONS COORDINATOR",
        "SYSTEMS ANALYST",
        "TRUCK HELPER",
        "RESERVATION OFFICER",
        "LIAISON OFFICER",
        "BUSBOY",
        "RECEIVING CLERK",
        "SYSTEMS DEVELOPER (COMPUTER)",
        "TEACHER ASSISTANT",
        "LEGAL ASSISTANT",
        "ENVIRONMENTAL SPECIALIST",
        "TRAINING COORDINATOR",
        "LEASING OFFICER",
        "AUDITOR",
        "SECOND MATE",
        "BUS CONDUCTOR",
        "SECURITY GUARD",
        "INTERIOR DESIGNER",
        "PAYROLL CLERK",
        "AUDIT ASSISTANT",
        "CORPORATE DIRECTOR",
        "HOUSEKEEPER (PRIVATE)",
        "BUTLER",
        "HOUSEMAID",
        "INSTRUCTOR",
        "STRUCTURAL STEEL WORKER (WORKSHOP)",
        "CREDIT/COLLECTION SPECIALIST",
        "EXPORT/IMPORT OFFICER",
        "QUALITY CONTROL ASSISTANT",
        "LABORER",
        "PERSONNEL CLERK",
        "PROJECT MANAGEMENT OFFICER",
        "INVENTORY CONTROL ANALYST",
        "CRANE OPERATOR",
        "TAX OFFICER",
        "NURSING AIDE",
        "FASHION DESIGNER",
        "PAYROLL MASTER",
        "LOANS ASSISTANT",
        "BILLING CLERK",
        "COMPUTER PROGRAMMER",
        "JAVA PROGRAMMER",
        "DENTAL ASSISTANT",
        "COMMUNITY RELATIONS OFFICER",
        "LABORATORY ASSISTANT",
        "MERCHANDISING OFFICER",
        "ART DIRECTOR",
        "PROJECT OFFICER",
        "MANAGEMENT SPECIALIST",
        "ELECTRICAL HELPER",
        "PHYSIOTHERAPIST",
        "BUILDING ADMINISTRATOR",
        "BIOLOGIST (GENERAL)",
        "BILL COLLECTOR",
        "MANAGEMENT ANALYST",
        "BUYER",
        "CANVASSER",
        "LAWYER",
        "CREATIVE WRITER",
        "EDITOR",
        "FOOD TECHNOLOGIST",
        "TAX SPECIALIST I (GOV)",
        "INFORMATION TECHNOLOGY CONSULTANT",
        "BRAID PRODUCTION MACHINE OPERATOR",
    ]

    print()
    print("=" * 80)
    print("RECRUITIX TITLE STANDARDIZATION TEST")
    print("=" * 80)

    for title in test_titles:

        result = standardize_title(
            title
        )

        print(
            f"{title:<55} "
            f"-> {result['career_category']:<25} "
            f"[{result['match_method']}]"
        )

    print()
    print("=" * 80)