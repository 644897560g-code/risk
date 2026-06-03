# LLM生成的在线APP分类规则库（修复版）

生成时间: 2026-04-26
学习方法: LLM_rule_learning_qwen3.6-plus
修复说明: 针对utility和religious类别重新学习（限制50个样本）

---

## social_entertainment
- 样本数: 3810
- 关键词: hiburan, mainan, sosial, kuis, tebak, gambar, warna, anak, balita, santai, lucu, ngobrol, seru, ringan, puzzle, match, blast, pop, sort, merge
- 正则模式: ^.*\.(puzzle|match|blast|pop|sort|merge|idle|tycoon|ludo|mahjong|solitaire|card|board|chess|domino|bingo|quiz|trivia|coloring|paint|draw|kids|baby|toddler).*, ^.*\.(short|drama|stream|live|meme|sticker|social|chat|video|music|radio|podcast|karaoke|dance|party|prank|fakechat|status|entertainment|casual|game(s)?).*, ^com\.(kigle\.cocobi|rvappstudios\.baby|gametion|halfbrick|miniclip|cedargames|fungames|turborocketgames|playtika|realmadridplay|netx|tvb|vk|quora|irccloud|alexa\.club|bm\.pulsagram|tuntun\.tt|youshort|reel\.short|dukulive|netflix|apple\.atve)\..*
- 品牌: Kigle Cocobi, RV App Studios, Gametion, Halfbrick, Miniclip, Netflix, VK, Tuntun TT, Dukulive

**推理逻辑**: 综合样本特征，social_entertainment 在印尼市场呈现“轻度化、碎片化、内容驱动”的特点。包名结构高度依赖功能描述词（如 puzzle, match, short, drama, stream, meme）和知名休闲/内容厂商前缀。通过组合关键词匹配、正则模式识别与品牌白名单，可高效覆盖休闲游戏、流媒体、社交互动及趣味工具四大子域。同时，通过排除金融、电商、系统工具及硬核游戏特征词...


---

## productivity
- 样本数: 770
- 关键词: absensi, presensi, eoffice, ekinerja, laporan, belajar, kasir, gudang, rumus, tutorial, catatan, keuangan, pinjaman, tagihan, gaji, karyawan, pegawai, sekolah, ujian, soal
- 正则模式: ^.*(office|docs|document|pdf|excel|word|ppt|spreadsheet).*$, ^.*(notes?|notepad|memo|diary|logbook|journal|checklist).*$, ^.*(finance|expense|budget|money|loan|emi|debt|cash|wallet|tracker|planner|calculator).*$, ^.*(attendance|absensi|presensi|hris|workday|portal|eoffice|ekinerja|laporan).*$, ^.*(learn|edu|belajar|tutorial|exam|quiz|school|class|course|lms).*$
- 品牌: wps, microsoft, evernote, atlassian, zoho, workday, salesforce, anydesk, kumon, classdojo

**推理逻辑**: 综合包名结构、关键词分布及业务场景，Productivity类别在印尼市场呈现明显的“办公文档+财务规划+考勤人事+教育学习+商业管理”五大核心特征。包名中大量使用office, notes, pdf, excel, absensi, presensi, finance, loan, calculator, learn, edu, pos, crm等词根，且印尼本土政务/企业应用高度依赖id.go...


---

## gambling
- 样本数: 561
- 关键词: judi, togel, hoki, gacor, putar, gaple, qiuqiu, domino, dana, duit, rp, prediksi, pusatmenang, kocok, semar, dewa, naga, slot, slots, poker
- 正则模式: ^com\.id\d+[a-z0-9]*\.ntla\d+.*$, ^com\.app\.cerb\.mc[a-z0-9]+$, .*(slot|slots|togel|judi|domino|qq|poker|bingo|blackjack|toto|casino|jackpot|spin|bet|rtp|hoki|gacor).*, .*(777|888|168|188|288|388|666|999|vip\d+).*, ^com\.(higgs|kamagames|ptfarm|sbotop|iqoption|olymptrade|seamless|nivalogic|bigcake|topfun|playvalve|mobilechess|appybuilder|slotempire|dorahoki|macanempire|tradewill|kotakkoin|mysterytag)\..*$
- 品牌: Higgs Domino, SBOBET, IQ Option / Olymp Trade, KamaGames / PTFarm, CERB / NTLA Framework

**推理逻辑**: 印尼赌博应用具有极强的命名规律：1）大量使用固定马甲框架（如 com.id[数字].ntla[数字] 和 com.app.cerb.mc[字母数字]），这是黑灰产批量打包的典型特征；2）高频使用博彩核心词（slot, togel, judi, domino, poker）及印尼本地化黑话（hoki, gacor, putar, gaple）；3）极度依赖吉利数字（777, 888, 168, 18...


---

## cash_loan
- 样本数: 262
- 关键词: pinjaman, pinjam, pinjol, kredit, tunai, cair, cicil, modal, kasbon, gaji, dana, uang, rupiah, cepat, kilat, mudah, amanah, pasti, plus, pintar
- 正则模式: ^.*(?:pinjam|pinjol|kredit|kredi|tunai|cair|cicil|modal|kasbon|gaji).*$, ^.*(?:loan|cash|credit|finance|fintech|fintek|pay|advance|salary).*$, ^.*(?:dana|uang|rupiah|dompet|wallet).*(?:pinjam|kredit|loan|cash|tunai|cair|cicil|modal|cepat|kilat|online|mudah|plus|pintar|amanah|pasti).*$, ^.*(?:cepat|kilat|fast|quick|mudah|easy|online|instant|now|today|jam|menit|detik).*(?:pinjam|kredit|loan|cash|tunai|cair|cicil|dana|uang|rupiah).*$
- 品牌: Kredit Pintar, Kredit Plus, CashAda, Cairin, Tunaiku, Indodana, AdaKami, KTA Kilat, Yesss Credit, Finplus

**推理逻辑**: 综合推理逻辑：印尼现金贷市场具有高度同质化的命名特征，开发者为追求SEO转化率和用户直观理解，普遍在包名中堆砌直白的金融借贷词汇。规则体系通过“核心借贷词（印尼语/英语）”、“资金+动作组合”、“速度/便捷修饰词”三层正则覆盖95%以上的样本。同时，结合已知头部品牌白名单提升判定置信度，并通过排除电子钱包、传统银行、投资理财等易混淆场景的负向规则，有效降低误判率。该规则集兼顾了高召回率（覆盖变体、...


---

## banking
- 样本数: 232
- 关键词: bank, mbanking, mobilebanking, digitalbank, livin, brimo, wondr, mybca, halobca, simobi, msmile, onemobileapp, netbank, revolut, commbank, maybank, hsbc, citi, dbank, uob
- 正则模式: ^id\.co\.(bri|bca|bni|btn|bsi|cimb|ocbc|permata|mega|panin|jago|blu|nobu|linebank|aladinbank|hibank|danabagus|sumut|jatim|jateng|lampung|kalsel|kalteng|kaltimtara|sulselbar|ntt|riau|sumut|sulut|bpr|bmt|koperasi|syariah|islamic|rekening|celengan|kredit|nasabah|mbanking|mobilebanking|digitalbank|livin|brimo|wondr|mybca|halobca|simobi|msmile|onemobileapp|netbank|revolut|commbank|maybank|hsbc|citi|dbank|uob|dbs|mnc|kbstar|bjb|panin|rekeningku|celenganku|kreditcard|merchant|agent|token|pay|wallet|coop|koperasi|syariah|islamic|bpr|bmt|fcu|cu|nasabah|rekening|celengan|kredit|mb|digital|banking)\..*, ^com\.(bca|btpn|dwidasa|kospin|koperasi|mbank|panin|simas|nobubank|hibank|dbank|uob|dbs|mnc|kbBukopin|lst|dev\.jakone|asabri|celenganku|rekeningku|trust|ammana|megasyariah|aladinbank|linebank|bcasyariah|bankmega|ocbcnisp|bankraya|bankfama|bankbkemobile|bankarthagraha|bankdki|bankntbsyariah|apps\.tkbmobileapps|revolut|commbank|maybank|hsbc|citi|dbank|uob|dbs|mnc|kbstar|bjb|panin|rekeningku|celenganku|kreditcard|merchant|agent|token|pay|wallet|coop|koperasi|syariah|islamic|bpr|bmt|fcu|cu|nasabah|rekening|celengan|kredit|mb|digital|banking)\..*, .*\.(mb|mobilebanking|digitalbank|livin|brimo|wondr|mybca|halobca|simobi|msmile|onemobileapp|netbank|revolut|commbank|maybank|hsbc|citi|dbank|uob|dbs|mnc|kbstar|bjb|panin|rekeningku|celenganku|kreditcard|merchant|agent|token|pay|wallet|coop|koperasi|syariah|islamic|bpr|bmt|fcu|cu|nasabah|rekening|celengan|kredit|mb|digital|banking)$, ^co\.id\.bankbsi\..*|^id\.bmri\..*|^id\.bni\..*|^id\.bions\..*|^id\.bankina\..*|^id\.aladinbank\..*|^id\.co\.linebank$|^id\.co\.bcasyariah\..*|^id\.co\.bankfama\..*|^id\.co\.bankbkemobile\..*|^id\.co\.bankarthagraha\..*|^id\.co\.bankdki\..*|^id\.co\.bankntbsyariah\..*|^id\.co\.bankraya\..*|^id\.co\.banklampung\..*|^id\.co\.banksultra\..*|^id\.co\.collega\..*|^id\.co\.bri\..*|^id\.co\.btn\..*|^id\.co\.bni\..*|^id\.co\.bca\..*|^id\.co\.cimbniaga\..*|^id\.co\.ocbc\..*|^id\.co\.permata\..*|^id\.co\.mega\..*|^id\.co\.panin\..*|^id\.co\.jago\..*|^id\.co\.blu\..*|^id\.co\.nobu\..*|^id\.co\.hibank\..*|^id\.co\.danabagus\..*|^id\.co\.sumut\..*|^id\.co\.jatim\..*|^id\.co\.jateng\..*|^id\.co\.lampung\..*|^id\.co\.kalsel\..*|^id\.co\.kalteng\..*|^id\.co\.kaltimtara\..*|^id\.co\.sulselbar\..*|^id\.co\.ntt\..*|^id\.co\.riau\..*|^id\.co\.sumut\..*|^id\.co\.sulut\..*|^id\.co\.bpr\..*|^id\.co\.bmt\..*|^id\.co\.koperasi\..*|^id\.co\.syariah\..*|^id\.co\.islamic\..*|^id\.co\.rekening\..*|^id\.co\.celengan\..*|^id\.co\.kredit\..*|^id\.co\.nasabah\..*|^id\.co\.mbanking\..*|^id\.co\.mobilebanking\..*|^id\.co\.digitalbank\..*|^id\.co\.livin\..*|^id\.co\.brimo\..*|^id\.co\.wondr\..*|^id\.co\.mybca\..*|^id\.co\.halobca\..*|^id\.co\.simobi\..*|^id\.co\.msmile\..*|^id\.co\.onemobileapp\..*|^id\.co\.netbank\..*|^id\.co\.revolut\..*|^id\.co\.commbank\..*|^id\.co\.maybank\..*|^id\.co\.hsbc\..*|^id\.co\.citi\..*|^id\.co\.dbank\..*|^id\.co\.uob\..*|^id\.co\.dbs\..*|^id\.co\.mnc\..*|^id\.co\.kbstar\..*|^id\.co\.bjb\..*|^id\.co\.panin\..*|^id\.co\.rekeningku\..*|^id\.co\.celenganku\..*|^id\.co\.kreditcard\..*|^id\.co\.merchant\..*|^id\.co\.agent\..*|^id\.co\.token\..*|^id\.co\.pay\..*|^id\.co\.wallet\..*|^id\.co\.coop\..*|^id\.co\.koperasi\..*|^id\.co\.syariah\..*|^id\.co\.islamic\..*|^id\.co\.bpr\..*|^id\.co\.bmt\..*|^id\.co\.fcu\..*|^id\.co\.cu\..*|^id\.co\.nasabah\..*|^id\.co\.rekening\..*|^id\.co\.celengan\..*|^id\.co\.kredit\..*|^id\.co\.mb\..*|^id\.co\.digital\..*|^id\.co\.banking\..*
- 品牌: BRI (Bank Rakyat Indonesia), BCA (Bank Central Asia), Mandiri (Bank Mandiri), BNI (Bank Negara Indonesia), BSI (Bank Syariah Indonesia), CIMB Niaga, BTN (Bank Tabungan Negara), Jago Digital Bank, OCBC NISP, Panin Bank

**推理逻辑**: 综合推理逻辑：上述规则基于232个印尼banking样本的包名结构与语义特征构建。核心判定依据为三点：1) 域名结构特征：印尼持牌银行高度统一使用 `id.co.[bank]`、`co.id.[bank]` 或 `com.[bank]` 格式，这是最可靠的强特征；2) 品牌与产品后缀：如 `brimo`, `livin`, `wondr`, `mybca`, `halobca`, `simobi`...


---

## shopping
- 样本数: 224
- 关键词: toko, beli, jual, grosir, lelang, warung, apotik, apotek, klik, mitra, poin, kartu, member, etalase, dagangan, niaga, superindo, alfamart, indomaret, blibli
- 正则模式: ^.*\.(shop|store|mart|mall|market|ecommerce|commerce|retail|trade|b2b|b2c|wholesale|grosir|toko|beli|jual|klik|mitra|seller|merchant|agent|fms|pda|lite|cart|checkout|dealer|ecomm|bid|bidder).*$, ^.*\.(loyalty|rewards|poin|member|card|gift|voucher|catalogue|ekatalog|etalase|coupon|qpon).*$, ^.*\.(shopee|tokopedia|bukalapak|lazada|blibli|zalora|alfamart|indomaret|familymart|circlek|lottemart|hypermart|superindo|matahari|erafone|informa|k24klik|sayurbox|pasarkuota|amazon|ebay|aliexpress|jd|taobao|coupang|wish|vova|11st|elevenst|kth|kshop|skmnc|gramedia|melawai|tunjunganplaza|pakuwon|summareconmall|lippomalls|aeon|pacificplace|styles|tangcity|gwk|moonhint|lpoint|getplus|holdr|prestasiretail|urbancoloyaltyapp|icemobile|albertheij|plants|broccolicart|brayamart|citramart|warungdigital|biggu|shopsavvy|onlineshoppinghub|on9store|elys|protius|zhiliaoapp|realmestore|mova|shopintar|mjs|astro|shopback|alibaba|airbnb|travelio|santika|archipelago|reddoorz|pegipegi|agoda|traveloka|loket|tiket|kudo|sinyee|babybus|astra|pinhome|btn|rumah123|caready|pasbid|smartbid|oto|moladin|kawanlama|ptmarketplaceio|jualxbeli|snapsell|snapcart).*$
- 品牌: Shopee, Tokopedia, Bukalapak, Lazada, Blibli, Alfamart / Indomaret, Zalora, Matahari / Erafone / Informa, Sayurbox / PasarKuota, Amazon / eBay / AliExpress / JD / Taobao

**推理逻辑**: 综合224个样本特征，印尼购物类APP包名呈现高度结构化与生态化特征：1) 核心词根明确且高频（shop/store/mart/mall/toko/beli/jual等），直接映射零售交易意图；2) 垂直场景细分清晰，涵盖综合电商、生鲜、美妆、数码、拍卖(lelang)、批发(grosir)、会员积分(loyalty/poin)及商家工具(seller/mitra)；3) 头部品牌包名高度统一（s...


---

## transportation
- 样本数: 170
- 关键词: ojol, ojek, krl, mrt, damri, pelni, kai, dishub, transjakarta, angkot, kereta, kapal, pesawat, kurir, logistik, ekspedisi, pengiriman, tiket, antar, jemput
- 正则模式: .*\.(driver|passenger|supir|sopir|penumpang)\..*, .*\.(logistics|courier|express|delivery|cargo|freight|tms|dispatch|tracking|ekspedisi|pengiriman|kurir)\..*, .*\.(transport|transit|transportasi|dishub|transjakarta|angkot|damri|pelni|kai|krl|mrt|bus|train|rail|ferry|ship|kapal|kereta)\..*, .*\.(taxi|ride|cab|ojol|ojek|ticket|booking|travel|trip|flight|airline|aviation|map|gps|navigation|route|drive|rental|car|motor|bike|scooter|etoll|eticket)\..*, .*\.(gojek|grab|maxim|bolt|bluebird|lalamove|deliveree|ritase|paxel|anteraja|kiriminaja|sicepat|lionparcel|traveloka|tiket|pegipegi|nusatrip|airasia|citilink|garuda|sriwijaya|pelita|waze|citymapper|skyscanner|wego|agoda|booking|trivago|ctrip|flightradar|shell|honda|toyota|suzuki|yamaha|nissan|byd)\..*
- 品牌: Gojek, Grab, Traveloka, Bluebird, KAI (Kereta Api Indonesia), SiCepat, Waze, AirAsia, Lalamove, TransJakarta

**推理逻辑**: 综合推理逻辑：上述规则基于170个印尼交通类APP样本的包名结构与业务语义提炼而成。通过提取高频角色词（driver/passenger）、业务词（logistics/transit/ticket）、印尼本土交通专有名词（ojol/krl/damri/pelni）及头部品牌标识，构建了覆盖网约车、物流货运、公共交通、航空铁路、导航地图及票务预订的全场景识别体系。正则表达式精准匹配包名中的核心语义段...


---

## fintech_lending
- 样本数: 116
- 关键词: kredit, gadai, cicil, dana, lending, paylater, fintech, p2p, lender, modal, agen, merchant, superapp, crowdfund, finpartner, credit, finance, loan, lending, paylater
- 正则模式: ^.*\.(credit|kredit|lending|loan|paylater|cicil|gadai|dana|fintech|p2p|lender|fif|homecredit|kredivo|akulaku|indodana|koinworks|bfi|aeoncredit|wom|adira|taf|finaccel|fazz|julo|kreditplus|edufund|crowdfund|finpartner|finetiks|finflex|finture|fin|modal|nasional|virtus|tentendigital|gradana|alami|motioncredit|capitalnet|danacita|crediseal|pefi|sewasam|ucollect|payjoy|kastfinance|momofin|cermati|myidscore|pegadaian|pcpexpress|cnaf|credibook|unicorn|kopnus|blicicil|payfazz|indopremier|one\.ifg|bridanareksasekuritas|ayovestpro|bfi\.agenttools|fusionmedia|olymptrade|bitget|bareksa|kredivoseller|finaccel\.lion|indodana\.onsite\.agent)\..*$, ^.*\.(agent|lender|merchant|partner|onsite|prod|dashboard|status|tools|preassessment|coll)\..*$, ^id\.co\..*\.(fif|bfi|wom|adira|taf|homecredit|pegadaian|edufund|myhomecredit|fifgroup)\..*$
- 品牌: Kredivo / Finaccel, Akulaku, Home Credit, Indodana, KoinWorks, FIF Group / WOM Finance / Adira / TAF, Pegadaian, BFI Finance, Aeon Credit

**推理逻辑**: 综合推理逻辑：印尼fintech_lending应用包名具有高度结构化特征。首先，核心业务词（credit/kredit/lending/loan/paylater/cicil/gadai）直接出现在包名中，是最高置信度信号；其次，头部品牌（Kredivo, Akulaku, Home Credit, Indodana, KoinWorks, FIF, Pegadaian等）具有强独占性，匹配即可...


---

## ewallet
- 样本数: 89
- 关键词: dompet, uang, kasir, kios, qris, emoney, mwallet, ewallet, dana, gopay, ovo, shopeepay, sakuku, flip, astrapay, bca, bni, telkom, posindonesia, wallet
- 正则模式: ^.*(?:wallet|pay|dana|gopay|ovo|shopeepay|emoney|qris|mwallet|ewallet|dompet|uang|crypto|coin|blockchain|remittance|transfer|kasir|kios).*, ^(?:com|id|io|app|vivapay|ovo)\.[a-z0-9_\.]*?(?:wallet|pay|dana|gopay|ovo|shopeepay|emoney|qris|mwallet|ewallet|dompet|uang|crypto|coin|blockchain|remittance|transfer|kasir|kios)[a-z0-9_\.]*?$, ^.*(?:merchant|kasir|kios|agent|aktivasi).*(?:dana|gopay|ovo|shopeepay|pay|wallet).*$
- 品牌: DANA, GoPay, OVO, ShopeePay, BCA Sakuku, Flip, Trust Wallet, Wise (TransferWise)

**推理逻辑**: 综合89个样本分析，印尼ewallet类别呈现高度一致的“品牌词+功能词”命名规律。核心判定逻辑基于三层过滤：1) 词法层：包名高频包含 wallet, pay, dana, gopay, ovo, emoney, qris, dompet, uang, crypto, coin 等支付/钱包专属词，这些词在印尼金融科技生态中具有强独占性；2) 结构层：符合 com./id./io. 域名前缀+核...


---

## utility
- 样本数: 50
- 关键词: penerjemah, terjemahan, kalkulator, pembersih, pengatur, jam, kunci, senter, tool, tools, reader, viewer, editor, camera, tracker, locator, gps, translator, control, launcher
- 正则模式: \.tools?\., \.(reader|viewer|editor|converter|calculator|translator|penerjemah)\., \.(tracker|locator|gps|compass|mirror|scanner|printer|backup|vault|cleaner|antivirus|downloader)\., org\.chromium\.webapk\., \.(control|launcher|keyboard|theme|wallpaper|clock|iot|service)\.
- 品牌: Microsoft, Lightricks, XE, Snow Corp

**推理逻辑**: 综合判定逻辑基于'功能单一性'与'系统/效率增强'两大核心特征。Utility类APP的包名命名高度规范化，通常采用'域名.功能词.子功能'或'品牌.工具类型'的结构。通过提取高频功能词（如reader, editor, tracker, downloader, penerjemah）构建正则模式，可精准覆盖文档处理、设备管理、系统优化、硬件控制等典型工具场景。同时，结合印尼语本地化特征词（如pe...


---

## religious
- 样本数: 50
- 关键词: dzikir, sholat, sholawat, kiblat, haji, umroh, zakat, fiqih, hijri, tasbih, iqra, maulid, khatolik, doa, murottal, manasik, pagipetang, terjemahan, tajwid, islami
- 正则模式: ^.*(?i)(quran|alquran|dzikir|sholat|sholawat|kiblat|qibla|prayer|adhan|azan|haji|umroh|zakat|fiqih|islami|islamic|muslim|tasbih|tasbeeh|iqra|maulid|khatolik|doa|murottal|manasik|hijri|namaz|ruqyah|salat).*$, ^.*(?i)(com\.(aplikita|paidevelop|tanxe|rumahzakat|muslimidia|islamiapps)|my\.id\.paksu).*$, ^.*(?i)(prayertimes|qibladirection|hijricalendar|digitaltasbeeh|arahkiblat|terjemahan|tajwid|kamusarab|kitab).*$
- 品牌: Muslim Pro, Aplikita, Paidevelop, Rumah Zakat, Hijrah Kami, Kakime Studio

**推理逻辑**: 综合推理逻辑：印尼religious类别APP高度集中于伊斯兰教（占比超95%），辅以少量天主教应用。判定规则以包名中的核心宗教词汇（印尼语/英语/阿拉伯语借词）为第一特征，结合特定开发商/品牌前缀进行交叉验证。正则表达式覆盖经典诵读、礼拜时间、朝向工具、朝觐指南、天课捐赠、宗教教育等核心场景。通过排除游戏、金融、社交、媒体等高频干扰词，确保规则在复杂包名环境下的准确率与召回率。该规则体系充分利用...


---

## food_delivery
- 样本数: 34
- 关键词: bakmi, boga, resto, kenangan, gofood, foody, food, delivery, eat, hungry, coffee, burger, pizza, kfc, starbucks, mcdelivery, driver, mobileapp
- 正则模式: ^.*\.(food|delivery|resto|eat|hungry|coffee|burger|pizza|bakmi|boga).*$, ^.*\.(gofood|foody|mcdelivery|ishangry|hungryhub|happyfresh|segari|yogiyo).*$, ^.*\.(driver|deliveryboy).*$, ^.*\.(kfc|starbucks|pizzahut|dominos|burgerking|popeyes|wingstop|hokben|chatime|kopikenangan|jagocoffee|flashcoffee|tomoro|sushitei|marugame|richeese|haidilao|holywings|mcdonalds|plato).*$
- 品牌: GoFood/Gojek, ShopeeFood, McDonald's, KFC, Pizza Hut, Kopi Kenangan, Hokben, HappyFresh/Segari, Domino's, Starbucks

**推理逻辑**: 综合推理逻辑：规则采用“核心业务词+平台标识+品牌白名单+运力端特征”的多维匹配策略。包名中的 food, delivery, resto, coffee 等直接反映业务属性；gofood, foody 等是印尼市场头部平台的强特征；国际/本土连锁品牌名具有极高唯一性；driver 等词覆盖外卖生态的配送端。配合明确的排除规则过滤游戏、金融、通用物流等干扰项，可确保在印尼市场环境下对 food_d...


---

## fake_gps
- 样本数: 29
- 关键词: fake, gps, location, mock, emulator, spoofer, faker, changer, coordinates, geolocation
- 正则模式: .*fake.*gps.*, .*mock.*location.*, .*gps.*emulator.*, .*location.*(changer|spoofer|faker).*, ^com\.(incorporateapps|webmajstr|rosteam|silentlexx|gavrikov|discipleskies|tinysoft|lexa)\..*
- 品牌: incorporateapps, webmajstr, rosteam, silentlexx

**推理逻辑**: 综合29个样本分析，fake_gps类应用的包名具有极强的语义指向性，几乎全部采用英文技术词汇组合。核心判定逻辑为：'伪造/模拟(fake/mock/emulator/spoofer)' + '定位/坐标(gps/location/coordinates)'。通过构建精准的正则表达式提取这些关键词组合，并结合已知高频开发者的品牌白名单，可实现高精度自动化判定。同时，通过设置明确的排除规则（过滤正规...


---

## clone_app
- 样本数: 28
- 关键词: cloner, dual, multi, paralel, ganda, aplikasi ganda, clone, cloner, cloneapp, appclone, phoneclone, whatsclone, dual, dualapp, dualspace, parallel, parallelspace, multiaccounts, multiple, blackbox
- 正则模式: .*(?:clone|cloner|cloneapp|appclone|phoneclone|whatsclone).*, .*(?:dual|dualapp|dualspace).*, .*(?:parallel|parallelspace).*, .*(?:multiaccounts|multiple).*, ^(com\.(lbe|ludashi|blackbox|redfinger|oasisfeng)|mochat)\..*
- 品牌: Huawei (hicloud/huawei), OPPO (coloros), Transsion (transsion), Parallel Space (lbe/excean), DualSpace (ludashi), BlackBox (blackbox), Island (oasisfeng), Redfinger (redfinger), GBWhatsApp (gbwhatsapp)

**推理逻辑**: 综合28个样本分析，clone_app的核心技术特征是'应用虚拟化容器'与'多实例并发运行'。包名命名高度依赖英文技术词根（clone, dual, parallel, multi），直接映射其底层实现逻辑。结合已知双开框架（Parallel Space, DualSpace, BlackBox, Island等）的固定包名前缀，可构建高置信度的模式匹配规则。印尼市场虽在应用商店描述中使用本地化词...


---

## app_store
- 样本数: 26
- 关键词: kita, store, market, appstore, appmarket, apk, xapk, mods, hub, vending, installer
- 正则模式: ^.*\.(store|market|appstore|appmarket)(\..*)?$, ^.*\b(apk|xapk)\b.*$, ^.*\b(mods?|happymod|apkpure|aptoide|taptap|getjar|uptodown)\b.*$, ^.*\b(vending|hub|installer|updater)\b.*$
- 品牌: TapTap, Aptoide, APKPure, HappyMod, Uptodown, GetJar, Poco Store, Huawei AppGallery

**推理逻辑**: 综合样本分析，app_store类别的核心特征是'应用聚合与分发'。其包名高度依赖'store'、'market'、'apk'、'appstore'等直接表明分发属性的词汇，或采用国际/区域知名商店品牌（如TapTap, Aptoide, APKPure）。通过正则匹配标准商店后缀、APK分发标识及已知品牌，可覆盖绝大多数第三方、官方及模组商店。结合排除规则过滤金融、博彩及独立应用，能有效避免与t...


---

## installment
- 样本数: 13
- 关键词: cicil, cicilan, dicicil, kredit, installment, paylater, creditcard
- 正则模式: ^.*\.(cicil|cicilan|dicicil).*$, ^.*\.(installment|paylater|creditcard).*$, ^.*finance.*$
- 品牌: atome, dana, cashea, adira, indodana, fifada

**推理逻辑**: 综合13个样本分析，印尼installment类APP的包名命名呈现高度规律性：1) 强烈依赖印尼语本土词汇'cicil/cicilan'作为核心标识，这是区分其他金融类别的最强特征；2) 广泛采用国际通用的'paylater'和'installment'，反映BNPL模式在印尼的普及；3) 品牌命名多采用'com.[brand].[service]'或'id.co.[brand]'结构，且常与'...


---
