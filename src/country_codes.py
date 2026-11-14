"""Hand-written map from UN M49 numeric codes to ISO3 codes.

The UN migrant stock file identifies countries by M49 numbers, while the
IMF and World Bank use ISO3 letters. This table links the two.

Safety check: next to each code we store a word that the UN country name
must contain. 02_build_database.py stops if a code points to a different
name than expected, so a typo here cannot silently map the wrong country.
Countries hosting migrants from our four countries that are NOT in this
table are reported in the data-quality log with their share.
"""

# M49 code: (ISO3 code, text that must appear in the UN name, lower case)
M49_TO_ISO3 = {
    4: ("AFG", "afghanistan"),
    8: ("ALB", "albania"),
    12: ("DZA", "algeria"),
    31: ("AZE", "azerbaijan"),
    32: ("ARG", "argentina"),
    36: ("AUS", "australia"),
    40: ("AUT", "austria"),
    48: ("BHR", "bahrain"),
    50: ("BGD", "bangladesh"),
    51: ("ARM", "armenia"),
    56: ("BEL", "belgium"),
    70: ("BIH", "bosnia"),
    76: ("BRA", "brazil"),
    100: ("BGR", "bulgaria"),
    112: ("BLR", "belarus"),
    124: ("CAN", "canada"),
    144: ("LKA", "sri lanka"),
    152: ("CHL", "chile"),
    156: ("CHN", "china"),
    170: ("COL", "colombia"),
    191: ("HRV", "croatia"),
    196: ("CYP", "cyprus"),
    203: ("CZE", "czech"),
    208: ("DNK", "denmark"),
    231: ("ETH", "ethiopia"),
    233: ("EST", "estonia"),
    246: ("FIN", "finland"),
    250: ("FRA", "france"),
    268: ("GEO", "georgia"),
    276: ("DEU", "germany"),
    300: ("GRC", "greece"),
    344: ("HKG", "hong kong"),
    348: ("HUN", "hungary"),
    352: ("ISL", "iceland"),
    356: ("IND", "india"),
    360: ("IDN", "indonesia"),
    364: ("IRN", "iran"),
    368: ("IRQ", "iraq"),
    372: ("IRL", "ireland"),
    376: ("ISR", "israel"),
    380: ("ITA", "italy"),
    392: ("JPN", "japan"),
    398: ("KAZ", "kazakhstan"),
    400: ("JOR", "jordan"),
    404: ("KEN", "kenya"),
    410: ("KOR", "korea"),
    414: ("KWT", "kuwait"),
    417: ("KGZ", "kyrgyz"),
    422: ("LBN", "lebanon"),
    428: ("LVA", "latvia"),
    440: ("LTU", "lithuania"),
    442: ("LUX", "luxembourg"),
    458: ("MYS", "malaysia"),
    470: ("MLT", "malta"),
    484: ("MEX", "mexico"),
    496: ("MNG", "mongolia"),
    498: ("MDA", "moldova"),
    499: ("MNE", "montenegro"),
    504: ("MAR", "morocco"),
    512: ("OMN", "oman"),
    524: ("NPL", "nepal"),
    528: ("NLD", "netherlands"),
    554: ("NZL", "new zealand"),
    566: ("NGA", "nigeria"),
    578: ("NOR", "norway"),
    586: ("PAK", "pakistan"),
    604: ("PER", "peru"),
    608: ("PHL", "philippines"),
    616: ("POL", "poland"),
    620: ("PRT", "portugal"),
    634: ("QAT", "qatar"),
    642: ("ROU", "romania"),
    643: ("RUS", "russia"),
    682: ("SAU", "saudi"),
    688: ("SRB", "serbia"),
    702: ("SGP", "singapore"),
    703: ("SVK", "slovakia"),
    704: ("VNM", "viet"),
    705: ("SVN", "slovenia"),
    710: ("ZAF", "south africa"),
    724: ("ESP", "spain"),
    752: ("SWE", "sweden"),
    756: ("CHE", "switzerland"),
    760: ("SYR", "syria"),
    762: ("TJK", "tajikistan"),
    764: ("THA", "thailand"),
    784: ("ARE", "emirates"),
    788: ("TUN", "tunisia"),
    792: ("TUR", "rkiye"),          # "Türkiye" (older files: "Turkey")
    795: ("TKM", "turkmenistan"),
    804: ("UKR", "ukraine"),
    807: ("MKD", "macedonia"),
    818: ("EGY", "egypt"),
    826: ("GBR", "united kingdom"),
    840: ("USA", "united states"),
    860: ("UZB", "uzbekistan"),
    862: ("VEN", "venezuela"),
}

# Alternative spellings accepted by the name check.
ALTERNATIVE_NAMES = {
    792: "turkey",
}


def name_matches(m49_code, un_name):
    """Return True if the UN name fits the name expected for this code."""
    text = str(un_name).lower()
    expected = M49_TO_ISO3[m49_code][1]
    if expected in text:
        return True
    alternative = ALTERNATIVE_NAMES.get(m49_code)
    return alternative is not None and alternative in text
