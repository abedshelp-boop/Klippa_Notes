"""
Islamic / Arabic vocabulary used as Keyterms Prompting hints for AssemblyAI's
Universal-3 Pro model. Up to 1000 terms supported.

Terms are written in their most common transliterated English form (the form
the speaker would actually pronounce, not Arabic script). Keyterms work by
biasing the speech recognizer toward these specific spellings, dramatically
reducing mistranscriptions of Islamic proper nouns and technical terminology.

Add new terms to the relevant category list below. The dedupe in
`get_keyterms()` is order-preserving — earlier categories win on collisions.
"""

# ── Core basics — reserved at the front of the budget ────────────────────────
# These are the ~60 most-uttered Islamic terms across general Muslim speech.
# The budget cap would otherwise starve them out when later categories are
# reached. Keep this list tight — every word here costs budget.
CORE_BASICS = [
    # Names of the divine / the Prophet
    "Allah", "Ar-Rahman", "Ar-Rahim", "Rabb", "Muhammad", "Rasulullah",
    "the Prophet", "sallallahu alayhi wa sallam", "subhanahu wa ta'ala",
    # Core prophets commonly mentioned as bare names
    "Isa", "Musa", "Ibrahim", "Yusuf", "Nuh", "Maryam",
    # Five pillars / core worship
    "Islam", "Iman", "Ihsan", "shahada", "salah", "zakat", "sawm", "hajj",
    "umrah", "du'a", "dhikr",
    # Core scripture vocab
    "Quran", "ayah", "surah", "hadith", "sunnah", "tafsir",
    # The Six Books shorthand
    "Sahih al-Bukhari", "Sahih Muslim",
    # Four caliphs + core Sahabah
    "Abu Bakr", "Umar", "Uthman", "Ali", "Khadijah", "Aisha", "Fatimah",
    # Core places
    "Makkah", "Madinah", "Kaaba", "Masjid al-Haram", "Masjid an-Nabawi",
    "Masjid al-Aqsa",
    # Core calendar
    "Ramadan", "Eid al-Fitr", "Eid al-Adha", "Hijra",
    # Core sects/schools the user specifically cares about
    "sunni", "shia", "sufi", "salafi", "wahhabi", "deobandi",
    "hanafi", "shafi'i", "maliki", "hanbali",
    "ash'ari", "maturidi", "athari",
    # Core theology / common phrases
    "tawhid", "shirk", "kufr", "ummah", "jihad",
    "bismillah", "alhamdulillah", "insha'Allah", "mashallah", "allahu akbar",
    "astaghfirullah",
]


# ── 99 Names of Allah (Asma ul-Husna) ─────────────────────────────────────────
NAMES_OF_ALLAH = [
    "Allah", "Ar-Rahman", "Ar-Rahim", "Al-Malik", "Al-Quddus", "As-Salam",
    "Al-Mu'min", "Al-Muhaymin", "Al-Aziz", "Al-Jabbar", "Al-Mutakabbir",
    "Al-Khaliq", "Al-Bari", "Al-Musawwir", "Al-Ghaffar", "Al-Qahhar",
    "Al-Wahhab", "Ar-Razzaq", "Al-Fattah", "Al-Alim", "Al-Qabid", "Al-Basit",
    "Al-Khafid", "Ar-Rafi", "Al-Mu'izz", "Al-Mudhill", "As-Sami", "Al-Basir",
    "Al-Hakam", "Al-Adl", "Al-Latif", "Al-Khabir", "Al-Halim", "Al-Azim",
    "Al-Ghafur", "Ash-Shakur", "Al-Ali", "Al-Kabir", "Al-Hafiz", "Al-Muqit",
    "Al-Hasib", "Al-Jalil", "Al-Karim", "Ar-Raqib", "Al-Mujib", "Al-Wasi",
    "Al-Hakim", "Al-Wadud", "Al-Majid", "Al-Ba'ith", "Ash-Shahid", "Al-Haqq",
    "Al-Wakil", "Al-Qawi", "Al-Matin", "Al-Wali", "Al-Hamid", "Al-Muhsi",
    "Al-Mubdi", "Al-Mu'id", "Al-Muhyi", "Al-Mumit", "Al-Hayy", "Al-Qayyum",
    "Al-Wajid", "Al-Wahid", "Al-Ahad", "As-Samad", "Al-Qadir", "Al-Muqtadir",
    "Al-Muqaddim", "Al-Mu'akhkhir", "Al-Awwal", "Al-Akhir", "Az-Zahir",
    "Al-Batin", "Al-Muta'ali", "Al-Barr", "At-Tawwab", "Al-Muntaqim",
    "Al-Afuww", "Ar-Ra'uf", "Malik al-Mulk", "Dhul-Jalali wal-Ikram",
    "Al-Muqsit", "Al-Jami", "Al-Ghani", "Al-Mughni", "Al-Mani", "Ad-Darr",
    "An-Nafi", "An-Nur", "Al-Hadi", "Al-Badi", "Al-Baqi", "Al-Warith",
    "Ar-Rashid", "As-Sabur",
    # Additional common references to Allah
    "Rabb", "Ar-Rabb", "Al-Ilah", "Al-Mawla", "Subhanahu wa ta'ala",
    "Azza wa jall", "Jalla wa ala", "Tabaraka wa ta'ala",
]

# ── Hadith collections ────────────────────────────────────────────────────────
HADITH_BOOKS = [
    # The Six Books (Kutub al-Sittah)
    "Sahih al-Bukhari", "Sahih Muslim", "Sunan Abi Dawud", "Jami at-Tirmidhi",
    "Sunan an-Nasa'i", "Sunan Ibn Majah",
    # Other major collections
    "Muwatta Imam Malik", "Musnad Ahmad", "Musnad Imam Ahmad",
    "Mustadrak al-Hakim", "Sahih Ibn Hibban", "Sahih Ibn Khuzaymah",
    "Sunan al-Bayhaqi", "Sunan al-Kubra", "Sunan al-Daraqutni",
    "Mu'jam al-Tabarani", "Mu'jam al-Kabir", "Mu'jam al-Awsat",
    "Mu'jam as-Saghir", "Musannaf Ibn Abi Shaybah", "Musannaf Abd al-Razzaq",
    "Sunan al-Darimi", "Sunan Sa'id ibn Mansur", "Ash-Shamail al-Muhammadiyah",
    "Riyad as-Salihin", "Bulugh al-Maram", "Mishkat al-Masabih",
    "Al-Adab al-Mufrad", "Al-Targhib wa al-Tarhib",
    "Forty Hadith of Imam Nawawi", "Arba'in Nawawi", "Sahih al-Jami",
    "Silsilat al-Ahadith as-Sahihah", "Silsilat al-Ahadith ad-Da'ifah",
]

# ── Imams, scholars, hadith compilers ────────────────────────────────────────
IMAMS_AND_SCHOLARS = [
    # Hadith compilers
    "Imam Bukhari", "Imam Muslim", "Imam Malik", "Imam Ahmad",
    "Imam at-Tirmidhi", "Imam Abu Dawud", "Imam an-Nasa'i", "Imam Ibn Majah",
    "Imam al-Bayhaqi", "Imam al-Daraqutni", "Imam al-Tabarani",
    "Imam Ibn Hibban", "Imam Ibn Khuzaymah", "Imam al-Hakim",
    "Imam al-Darimi", "Imam Abd ar-Razzaq",
    # Founders of madhhabs
    "Imam ash-Shafi'i", "Imam Abu Hanifa", "Imam Ja'far as-Sadiq",
    # Major classical scholars
    "Imam an-Nawawi", "Imam Ibn Hajar", "Ibn Hajar al-Asqalani",
    "Imam adh-Dhahabi", "Imam Ibn Kathir", "Imam at-Tabari",
    "Imam al-Qurtubi", "Imam as-Suyuti", "Imam al-Ghazali",
    "Imam ar-Razi", "Imam Fakhr ad-Din ar-Razi", "Imam al-Bayhaqi",
    "Imam Ibn Abd al-Barr", "Imam al-Baghawi", "Imam ash-Shawkani",
    # Hanbali school
    "Ibn Taymiyyah", "Sheikh al-Islam Ibn Taymiyyah", "Ibn al-Qayyim",
    "Ibn al-Qayyim al-Jawziyyah", "Ibn Rajab al-Hanbali", "Ibn Qudamah",
    "Imam Ibn Qudamah",
    # Modern / contemporary scholars often referenced
    "Sheikh Muhammad ibn Abd al-Wahhab", "Sheikh al-Albani",
    "Muhammad Nasir ad-Din al-Albani", "Sheikh Ibn Baz",
    "Sheikh Abd al-Aziz ibn Baz", "Sheikh Ibn Uthaymin",
    "Muhammad ibn Salih al-Uthaymin", "Sheikh Salih al-Fawzan",
    "Sheikh al-Fawzan", "Sheikh Muqbil", "Sheikh Rabi al-Madkhali",
    "Sheikh Yasir Qadhi", "Sheikh Hamza Yusuf", "Sheikh Omar Suleiman",
    # Sufi luminaries (so they're recognized too, regardless of stance)
    "Imam al-Ghazali", "Ibn Arabi", "Jalal ad-Din Rumi", "Abd al-Qadir Jilani",
    "Sheikh Abd al-Qadir al-Jilani",
    # Honorific markers commonly attached to scholar names
    "rahimahullah", "rahimahumullah", "hafizahullah", "hafizahumullah",
]

# ── Schools of thought, sects, movements ─────────────────────────────────────
SCHOOLS_AND_SECTS = [
    # Sunni / Shia divide
    "sunni", "shia", "ahl as-sunnah", "ahl as-sunnah wal-jama'ah", "ahl al-bayt",
    # Madhhabs
    "hanafi", "shafi'i", "maliki", "hanbali", "ja'fari", "zaydi", "ibadi",
    "madhhab", "madhahib",
    # Theological schools
    "ash'ari", "maturidi", "athari", "atharis", "ahl al-hadith",
    "mu'tazila", "mutazilite", "kharijite", "khariji", "khawarij",
    "jabriyah", "qadariyah", "murji'ah",
    # Sufi orders / sufism
    "sufi", "sufiyya", "tasawwuf", "tariqah", "turuq", "naqshbandi",
    "qadiri", "shadhili", "chishti", "tijani", "mevlevi",
    # Modern movements / labels
    "wahhabi", "wahhabism", "salafi", "salafiyyah", "deobandi", "deobandis",
    "barelvi", "barelvis", "tablighi", "tablighi jamaat", "ikhwan",
    "ikhwan al-muslimin", "muslim brotherhood", "madhkhali", "madhkhalism",
    "jihadi", "jihadism", "modernist", "traditionalist",
]

# ── Aqidah / theology ────────────────────────────────────────────────────────
AQIDAH_TERMS = [
    "aqidah", "aqeedah", "iman", "islam", "ihsan", "tawhid", "tawheed",
    "tawhid ar-rububiyyah", "tawhid al-uluhiyyah", "tawhid al-asma was-sifat",
    "shirk", "shirk akbar", "shirk asghar", "kufr", "nifaq", "munafiq",
    "kafir", "mushrik", "murtad", "irtidad", "ridda",
    "taqwa", "sabr", "tawakkul", "ikhlas", "riya", "ujb",
    "qadar", "qadr", "qada wa qadar", "iradah", "iradah kawniyyah",
    "iradah shar'iyyah",
    "asma was-sifat", "ta'wil", "tafwid", "tashbih", "ta'til",
    "akhirah", "yawm al-qiyamah", "yawm ad-din", "ba'th", "hisab",
    "mizan", "sirat", "shafa'ah", "intercession",
    "ruh", "nafs", "qalb", "fitrah", "amanah", "khilafah", "istikhlaf",
    "al-ghayb", "unseen", "wahy", "revelation", "nubuwwah", "risalah",
    "khatm an-nubuwwah", "isma", "ismah",
]

# ── Worship / ibadat ─────────────────────────────────────────────────────────
WORSHIP_TERMS = [
    # Five pillars
    "shahada", "salah", "salat", "zakat", "sawm", "siyam", "hajj", "umrah",
    # Prayer terminology
    "fajr", "dhuhr", "asr", "maghrib", "isha", "tahajjud", "qiyam al-layl",
    "witr", "duha", "ishraq", "tarawih", "taraweeh", "qiyam ramadan",
    "sajdah", "ruku", "qiyam", "tashahhud", "tasleem", "tasbih",
    "rak'ah", "raka'at", "jama'ah", "imamah", "iqtida",
    "qibla", "qiblah", "adhan", "iqamah", "khutbah", "khateeb", "minbar",
    "musalla", "mihrab",
    # Purification
    "wudu", "wudhu", "ghusl", "tayammum", "istinja", "najasah", "taharah",
    "hadath", "janabah", "haid", "nifas",
    # Fasting / Ramadan-related
    "suhoor", "iftar", "iftaar", "sehri", "i'tikaf", "itikaaf", "lailat al-qadr",
    "laylat al-qadr",
    # Hajj / Umrah
    "ihram", "tawaf", "sa'i", "wuquf", "talbiyah", "labbayk", "ramy",
    "halq", "taqsir", "hady", "qurban", "udhiyah", "miqat",
    # Dua, dhikr, recitation
    "du'a", "dua", "dhikr", "tasbih", "tahmid", "takbir", "tahlil",
    "subhanallah", "alhamdulillah", "allahu akbar", "la ilaha illa Allah",
    "astaghfirullah", "bismillah", "audhu billahi", "ta'awwudh", "basmalah",
    "hawqalah", "la hawla wa la quwwata illa billah",
    # Charity beyond zakat
    "sadaqah", "infaq", "waqf", "khums", "fitrah", "zakat al-fitr",
]

# ── Quran terminology ────────────────────────────────────────────────────────
QURAN_TERMS = [
    "Quran", "Qur'an", "al-Quran", "al-Qur'an al-Karim", "Mushaf",
    "ayah", "ayat", "surah", "surat", "juz", "ajza", "hizb", "manzil",
    "ruku", "rub al-hizb",
    "tafsir", "tafseer", "ta'wil", "asbab al-nuzul", "asbab an-nuzul",
    "naskh", "mansukh", "nasikh", "muhkam", "mutashabih",
    "makki", "madani", "makki and madani",
    "tajwid", "tajweed", "qira'at", "qira'a", "qari", "qura", "hifz", "hafiz",
    "huffaz", "tadabbur",
    "isra", "mi'raj", "isra wal-mi'raj",
    # Famous surah names commonly mentioned
    "Surah al-Fatihah", "Al-Fatihah", "Surah al-Baqarah", "Al-Baqarah",
    "Surah Al Imran", "Surah an-Nisa", "Surah al-Ma'idah", "Surah al-An'am",
    "Surah al-A'raf", "Surah al-Anfal", "Surah at-Tawbah", "Surah Yunus",
    "Surah Hud", "Surah Yusuf", "Surah Ibrahim", "Surah al-Hijr",
    "Surah an-Nahl", "Surah al-Isra", "Surah al-Kahf", "Surah Maryam",
    "Surah Ta-Ha", "Surah al-Anbiya", "Surah al-Hajj", "Surah al-Mu'minun",
    "Surah an-Nur", "Surah al-Furqan", "Surah ash-Shu'ara", "Surah Yasin",
    "Yaseen", "Surah ar-Rahman", "Surah al-Waqi'ah", "Surah al-Hadid",
    "Surah al-Mulk", "Surah al-Jumu'ah", "Surah al-Ikhlas", "Surah al-Falaq",
    "Surah an-Nas", "Ayat al-Kursi", "Mu'awwidhatayn",
]

# ── Fiqh, usul, legal terminology ────────────────────────────────────────────
FIQH_TERMS = [
    "fiqh", "usul al-fiqh", "usul", "furoo", "furu", "qa'idah", "qawa'id",
    "qawa'id fiqhiyyah", "maslaha", "mafsada", "maqasid", "maqasid ash-shari'ah",
    "shari'ah", "shariah", "hukm", "ahkam",
    "fard", "fard ayn", "fard kifayah", "wajib", "sunnah", "sunnah mu'akkadah",
    "mustahabb", "mandub", "mubah", "makruh", "haram", "halal", "tahrim",
    "tahlil", "kara'ah",
    "ijtihad", "mujtahid", "taqlid", "ittiba", "muqallid",
    "ijma", "qiyas", "istihsan", "istislah", "istishab", "urf", "sadd adh-dhara'i",
    "dalil", "adillah", "hujjah", "burhan", "bayyinah", "qarinah",
    "nass", "zahir", "mujmal", "mubayyan", "mafhum", "mantuq",
    "amr", "nahy", "ibahah",
    "bid'ah", "bidah", "muhdath", "ihdath",
    "fatwa", "fatawa", "mufti", "qadi", "qada", "qadhi", "qadis",
    "shahid", "shuhud", "bayyinah", "yamin", "qasam",
    # Marriage, family, transactions
    "nikah", "talaq", "khula", "iddah", "mahr", "walimah", "mahram",
    "mut'ah", "polygamy", "polygyny",
    "riba", "gharar", "maysir", "qimar", "halal income",
    "bay", "buyu", "ijarah", "mudarabah", "musharakah", "murabaha",
    "salam", "istisna", "wakalah", "kafalah", "rahn", "hawalah",
    # Inheritance
    "mirath", "mirath al-fara'id", "fara'id", "wasiyyah",
]

# ── Phrases, honorifics, common expressions ──────────────────────────────────
PHRASES_AND_HONORIFICS = [
    # Salawat on the Prophet
    "sallallahu alayhi wa sallam", "salla Allahu alayhi wa sallam",
    "peace be upon him", "alayhi salatu was-salam",
    # On other prophets
    "alayhi salam", "alayhim salam",
    # On companions
    "radi Allahu anhu", "radhiallahu anhu", "radi Allahu anha",
    "radi Allahu anhum", "radi Allahu anhuma",
    # On scholars / pious
    "rahimahullah", "rahmatullahi alayh", "rahmatullahi alayha",
    "hafizahullah", "qaddasa Allah sirrahu",
    # On Allah
    "subhanahu wa ta'ala", "azza wa jall", "jalla wa ala", "tabaraka wa ta'ala",
    "subhana Allah", "ta'ala", "subhanahu",
    # Common phrases
    "insha'Allah", "in sha Allah", "mashallah", "ma sha Allah",
    "alhamdulillah", "subhanallah", "astaghfirullah", "astaghfiru Allah",
    "bismillah", "bismillah ar-Rahman ar-Rahim", "bismillahi r-rahmani r-rahim",
    "audhu billahi min ash-shaytan ar-rajim", "ta'awwudh",
    "la ilaha illa Allah", "shahadatayn",
    "muhammadun rasul Allah", "Muhammad rasul Allah",
    "allahu akbar", "Allahumma", "barakAllahu feek", "barak Allahu feek",
    "jazakAllahu khayran", "jazak Allahu khayran",
    "wallahu a'lam", "Allahu alam", "wallahu ta'ala alam",
    "la hawla wa la quwwata illa billah", "hasbunallahu wa ni'mal wakil",
    "inna lillahi wa inna ilayhi raji'un", "inna lillahi", "ya Allah",
    "Allahumma ameen", "ameen", "amin",
    "fi sabeelillah", "fi sabilillah",
]

# ── Sahabah and major early Muslim figures ───────────────────────────────────
SAHABAH = [
    # The Four Caliphs
    "Abu Bakr", "Abu Bakr as-Siddiq", "Umar", "Umar ibn al-Khattab",
    "Umar al-Faruq", "Uthman", "Uthman ibn Affan", "Ali", "Ali ibn Abi Talib",
    "Ameer al-Mu'mineen", "Amir al-Mu'minin",
    # Wives of the Prophet (Mothers of the Believers)
    "Khadijah", "Khadija bint Khuwaylid", "Aisha", "Aishah",
    "Aisha bint Abi Bakr", "Hafsa", "Hafsah bint Umar", "Zaynab",
    "Umm Salama", "Umm Habiba", "Maymunah", "Safiyyah", "Juwayriyyah",
    "Ummahat al-Mu'minin",
    # Children of the Prophet
    "Fatimah", "Fatima az-Zahra", "Zaynab bint Muhammad", "Ruqayyah",
    "Umm Kulthum",
    # Other prominent companions
    "Hasan", "Hasan ibn Ali", "Husayn", "Husayn ibn Ali", "Husain",
    "Hamza", "Hamzah ibn Abd al-Muttalib", "Abbas", "al-Abbas",
    "Bilal", "Bilal ibn Rabah", "Khalid ibn al-Walid", "Sayf Allah",
    "Salman al-Farisi", "Suhayb ar-Rumi", "Abu Hurayrah", "Abu Hurairah",
    "Ibn Abbas", "Abdullah ibn Abbas", "Ibn Umar", "Abdullah ibn Umar",
    "Ibn Mas'ud", "Abdullah ibn Mas'ud", "Anas ibn Malik",
    "Ubayy ibn Ka'b", "Mu'adh ibn Jabal", "Abu Dharr", "Abu Dharr al-Ghifari",
    "Talhah", "Talha", "Az-Zubayr", "Zubayr ibn al-Awwam",
    "Sa'd ibn Abi Waqqas", "Said ibn Zayd", "Abu Ubaydah",
    "Abu Ubaydah ibn al-Jarrah", "Mu'awiyah", "Mu'awiyah ibn Abi Sufyan",
    "Amr ibn al-As", "Ja'far", "Ja'far ibn Abi Talib", "Aqil",
    # Categories
    "Sahabah", "Sahabi", "Tabi'in", "Tabi'un", "Tabi at-Tabi'in",
    "Salaf", "Salaf as-Salih", "Khulafa ar-Rashidun", "Rashidun",
    "Ahl al-Bayt", "Banu Hashim",
]

# ── Prophets ─────────────────────────────────────────────────────────────────
PROPHETS = [
    "Nabi", "Rasul", "Rasulullah", "Nabiyyullah",
    "Muhammad", "Ahmad", "Mustafa", "the Prophet", "Khatam an-Nabiyyin",
    "Nabi Adam", "Adam", "Nabi Idris", "Idris", "Nabi Nuh", "Nuh", "Noah",
    "Nabi Hud", "Hud", "Nabi Salih", "Salih", "Nabi Ibrahim", "Ibrahim",
    "Khalil Allah", "Nabi Lut", "Lut", "Nabi Ismail", "Isma'il",
    "Nabi Ishaq", "Ishaq", "Nabi Ya'qub", "Ya'qub", "Israil",
    "Nabi Yusuf", "Yusuf", "Nabi Ayyub", "Ayyub", "Nabi Shu'ayb", "Shu'ayb",
    "Nabi Musa", "Musa", "Kalim Allah", "Nabi Harun", "Harun",
    "Nabi Dawud", "Dawud", "Da'ud", "Nabi Sulaiman", "Sulayman",
    "Nabi Ilyas", "Ilyas", "Nabi al-Yasa", "al-Yasa", "Nabi Yunus", "Yunus",
    "Nabi Zakariyya", "Zakariyya", "Zakariya", "Nabi Yahya", "Yahya",
    "Nabi Isa", "Isa ibn Maryam", "Ruh Allah", "Maryam",
    "Ulul Azm", "Ulu al-Azm",
]

# ── Places ───────────────────────────────────────────────────────────────────
PLACES = [
    "Makkah", "Mecca", "Madinah", "Medina", "Madinat ar-Rasul",
    "Masjid al-Haram", "Masjid an-Nabawi", "Masjid al-Aqsa", "Bait al-Maqdis",
    "al-Quds", "Jerusalem",
    "Kaaba", "Ka'bah", "Hajar al-Aswad", "Black Stone", "Maqam Ibrahim",
    "Hijr Ismail", "Multazam", "Zamzam", "well of Zamzam",
    "Safa", "Marwa", "Mount Safa", "Mount Marwa",
    "Arafah", "Arafat", "Mount Arafat", "Mina", "Muzdalifah", "Jabal ar-Rahmah",
    "Hira", "Cave of Hira", "Jabal an-Nur", "Thawr", "Cave of Thawr",
    "Uhud", "Mount Uhud", "Khaybar", "Badr", "Hudaybiyyah", "Ta'if",
    "Najran", "Sham", "Yemen", "Hijaz", "Tihamah", "Najd",
    "Kufah", "Basra", "Baghdad", "Cairo", "Damascus", "Constantinople",
    "Andalusia", "Cordoba", "Granada",
    # Afterlife realms
    "Jannah", "Paradise", "Jannat al-Firdaws", "Jannat Adn", "Jahannam",
    "Hellfire", "Naar", "Barzakh", "Sirat", "Hawd", "Hawd al-Kawthar",
]

# ── Calendar, key days, events ───────────────────────────────────────────────
CALENDAR = [
    "Hijri", "Hijra", "Hijrah", "AH", "Anno Hegirae",
    # Islamic months
    "Muharram", "Safar", "Rabi al-Awwal", "Rabi al-Thani", "Rabi ul-Awwal",
    "Rabi ul-Akhir", "Jumada al-Ula", "Jumada al-Thaniyah", "Jumada al-Akhirah",
    "Rajab", "Sha'ban", "Shaban", "Ramadan", "Ramadhan", "Shawwal",
    "Dhul-Qadah", "Dhul Qa'dah", "Dhul-Hijjah", "Dhul Hijjah",
    # Sacred months
    "Ashhur al-Hurum", "sacred months",
    # Key days
    "Yawm al-Jumu'ah", "Friday", "Yawm Arafah", "Day of Arafah",
    "Yawm an-Nahr", "Yawm at-Tarwiyyah", "Ayyam at-Tashreeq",
    "Ashura", "10th of Muharram",
    "Laylat al-Qadr", "Night of Power", "Laylat al-Bara'ah",
    "Eid al-Fitr", "Eid al-Adha", "Eid", "Mawlid", "Mawlid an-Nabi",
    "Isra wal-Mi'raj",
]

# ── Movements, concepts, miscellaneous ───────────────────────────────────────
MISCELLANEOUS = [
    # Governance / political
    "khilafah", "caliphate", "khalifah", "caliph", "amir", "ameer",
    "imamah", "wilayah", "ulu al-amr", "ahl al-hall wal-aqd",
    "shura", "consultation", "bay'ah", "pledge",
    "ummah", "millah", "jama'ah",
    # Conflict / jihad
    "jihad", "mujahid", "mujahidin", "ribat", "shahid", "shahadah", "martyr",
    "fitnah", "harb", "ghazwa", "sariyah", "silm", "sulh", "hudna",
    "dar al-harb", "dar al-islam",
    # Treatment of others
    "dhimmi", "ahl adh-dhimmah", "ahl al-kitab", "people of the book",
    "jizyah", "kharaj", "fai", "ghanima",
    # Ranks of belief / disbelief
    "muslim", "mu'min", "kafir", "munafiq", "mushrik", "musa'al",
    "fasiq", "zindiq", "munkir",
    # Dawah and education
    "dawah", "da'wah", "da'i", "dai", "tabligh", "irshad", "naseehah",
    "nasihah", "tarbiyah", "tazkiyah",
    # Knowledge categories
    "ilm", "ulum", "mufassir", "mufassirun", "muhaddith", "muhaddithin",
    "faqih", "fuqaha", "mutakallim", "mutakallimun", "ulama", "ulema",
    "talib al-ilm", "tullab al-ilm", "sheikh", "shaykh", "ustadh", "ustaz",
    "imam", "mawlana", "maulana", "hafiz", "qari",
    # Ethics / character
    "akhlaq", "adab", "muruwwah", "futuwwah", "haya", "hayah",
    "amanah", "sidq", "sadiq", "kidhb", "ghibah", "gheebah", "namimah",
    "buhtan", "ghadab", "hilm",
    # Spiritual states
    "khushu", "khudu", "khashyah", "muraqabah", "muhasabah",
    "tawbah", "inabah", "yaqeen", "yaqin",
    # Miscellaneous popular
    "barakah", "hikmah", "wisdom", "rizq", "ajr", "thawab", "hasanat",
    "sayyi'at", "sins", "ma'siya", "fasad",
    "shaytan", "iblis", "jinn", "mala'ikah", "angels",
    "Jibreel", "Jibril", "Mikail", "Israfil", "Izrail",
    # Often-mentioned classical works
    "Tafsir Ibn Kathir", "Tafsir at-Tabari", "Tafsir al-Qurtubi",
    "Tafsir al-Jalalayn", "Fath al-Bari", "Sharh Sahih Muslim",
    "Majmu al-Fatawa", "Zad al-Ma'ad", "Al-Muwafaqat", "Ihya Ulum ad-Din",
    "Al-Risalah", "Al-Umm", "Bidayat al-Mujtahid", "Al-Mughni",
    "Kitab at-Tawhid",
]


def get_keyterms(max_words: int = 750) -> list[str]:
    """Deduplicated, order-preserving keyterms list, capped by total word
    count (not by entry count).

    AssemblyAI's Universal-3 Pro officially allows 1000 words in
    `keyterms_prompt`, but there's also a 2672-token hard limit and
    transliterated Arabic terms tokenize heavy (~3+ tokens/word vs ~1.3 for
    plain English) — so 750 words is the safe practical ceiling for our
    vocabulary. The API rejects anything tighter with "prompt too long".

    Earlier categories (CORE_BASICS, honorifics, hadith books) win when the
    budget runs out, so the most authoritative vocabulary is always present.
    """
    # Ordered by priority: high-frequency / high-mistranscription-risk first
    # so the word budget never starves out the vocabulary you actually need.
    # Obscure Names of Allah, niche Sahabah, and miscellanea come last because
    # Whisper already handles many of them adequately.
    # CORE_BASICS goes first so the 60-odd most-uttered terms are never cut.
    # The rest is ordered by priority: high-frequency / high-mistranscription-
    # risk first so the word budget doesn't starve out the vocabulary you
    # actually need. Obscure Names of Allah and miscellanea come last.
    all_terms = (
        CORE_BASICS
        + PHRASES_AND_HONORIFICS   # "sallallahu alayhi wa sallam" etc
        + HADITH_BOOKS             # "Sahih al-Bukhari" mistranscriptions hurt
        + IMAMS_AND_SCHOLARS       # imam names frequently mangled
        + SCHOOLS_AND_SECTS        # user priority: sufi, deobandi, ash'ari
        + PROPHETS                 # Muhammad, Ibrahim, Musa, Isa
        + PLACES                   # Makkah, Madinah, Kaaba
        + CALENDAR                 # Ramadan, Eid, Muharram
        + QURAN_TERMS              # surah names + tafsir vocab
        + WORSHIP_TERMS
        + AQIDAH_TERMS
        + FIQH_TERMS
        + NAMES_OF_ALLAH           # most already in Whisper's training data
        + SAHABAH
        + MISCELLANEOUS            # fills remaining budget
    )
    seen: set[str] = set()
    out: list[str] = []
    word_total = 0
    for term in all_terms:
        # Case-insensitive dedupe, preserve original casing in output.
        key = term.lower()
        if key in seen:
            continue
        words = len(term.split())
        if word_total + words > max_words:
            # Skip this term and keep trying — a shorter later term may still fit.
            continue
        seen.add(key)
        out.append(term)
        word_total += words
    return out
