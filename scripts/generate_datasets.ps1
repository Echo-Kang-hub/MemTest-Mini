$root = "d:\FileDownload\Projects\MemTest-Mini\datasets"

# ---------- Extraction: 30 cases ----------
$extraction = @(
  @{test_id="ext_001"; type="extraction"; description="extract allergy"; turns=@(@{role="user"; content="I am a bit tired today. By the way, I am severely allergic to seafood."}); expected_memory_contains=@("seafood", "allergic"); require_all=$false},
  @{test_id="ext_002"; type="extraction"; description="extract profile"; turns=@(@{role="user"; content="My name is Leo. I am a software engineer and I work in Beijing."}); expected_memory_contains=@("Leo","software engineer","Beijing"); require_all=$false},
  @{test_id="ext_003"; type="extraction"; description="extract pet info"; turns=@(@{role="user"; content="I have a corgi named Wangcai."}); expected_memory_contains=@("Wangcai","corgi"); require_all=$false},
  @{test_id="ext_004"; type="extraction"; description="extract diet"; turns=@(@{role="user"; content="I am mostly vegetarian and avoid red meat."}); expected_memory_contains=@("vegetarian"); require_all=$false},
  @{test_id="ext_005"; type="extraction"; description="extract birthday"; turns=@(@{role="user"; content="My birthday is October 15."}); expected_memory_contains=@("October 15"); require_all=$true}
)

for ($i=6; $i -le 30; $i++) {
  $n = '{0:d3}' -f $i
  $city = @("Shanghai","Shenzhen","Hangzhou","Chengdu","Wuhan")[$i % 5]
  $job = @("product manager","photographer","designer","teacher","data analyst")[$i % 5]
  $hobby = @("running","swimming","badminton","hiking","reading")[$i % 5]
  $allergy = @("peanut","mango","shrimp","crab","milk")[$i % 5]
  $extraction += @{
    test_id = "ext_$n"
    type = "extraction"
    description = "batch extraction case_$n"
    turns = @(
      @{role="user"; content="I currently live in $city and work as a $job. I like $hobby and I am allergic to $allergy."},
      @{role="user"; content="The weather is nice today. Please remember these details."}
    )
    expected_memory_contains = @($city, $job, $allergy)
    require_all = $false
  }
}
$extraction | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $root "extraction_tests.json") -Encoding utf8

# ---------- Retrieval: 30 cases ----------
$retrieval = @(
  @{test_id="ret_001"; type="retrieval"; description="retrieve dog name"; setup=@(@{role="user"; content="I have a corgi named Wangcai."},@{role="user"; content="Nice weather today."}); query="What is my dog's name?"; expected_response_contains=@("Wangcai"); require_all=$true},
  @{test_id="ret_002"; type="retrieval"; description="retrieve city"; setup=@(@{role="user"; content="I currently live in Shanghai Pudong."},@{role="user"; content="Recommend me a song."}); query="Which city do I live in?"; expected_response_contains=@("Shanghai"); require_all=$true},
  @{test_id="ret_003"; type="retrieval"; description="retrieve allergy"; setup=@(@{role="user"; content="I am allergic to peanut."},@{role="user"; content="Tell me a joke."}); query="What am I allergic to?"; expected_response_contains=@("peanut"); require_all=$true},
  @{test_id="ret_004"; type="retrieval"; description="retrieve job"; setup=@(@{role="user"; content="I am a freelance photographer."},@{role="user"; content="Recommend a movie."}); query="What is my job?"; expected_response_contains=@("photographer"); require_all=$true},
  @{test_id="ret_005"; type="retrieval"; description="retrieve birthday"; setup=@(@{role="user"; content="My birthday is October 15."},@{role="user"; content="Translate this sentence."}); query="When is my birthday?"; expected_response_contains=@("October 15"); require_all=$true}
)

for ($i=6; $i -le 30; $i++) {
  $n = '{0:d3}' -f $i
  $pet = @("Naitang","Pudding","Snowball","Tiger","Doubou")[$i % 5]
  $petType = @("cat","corgi","golden retriever","parrot","rabbit")[$i % 5]
  $city = @("Nanjing","Suzhou","Xian","Changsha","Qingdao")[$i % 5]
  $lang = @("Japanese","Spanish","French","German","Korean")[$i % 5]
  $retrieval += @{
    test_id = "ret_$n"
    type = "retrieval"
    description = "batch retrieval case_$n"
    setup = @(
      @{role="user"; content="I have a $petType named $pet and I live in $city."},
      @{role="user"; content="I have been learning $lang for 30 minutes every day."},
      @{role="user"; content="There is a lot of news today, let's talk about something else."}
    )
    query = "Tell me my pet name and my city."
    expected_response_contains = @($pet, $city)
    require_all = $false
  }
}
$retrieval | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $root "retrieval_tests.json") -Encoding utf8

# ---------- Update: 30 cases ----------
$update = @(
  @{test_id="upd_001"; type="update"; description="job update"; turns=@(@{role="user"; content="I am currently a programmer."},@{role="user"; content="I changed my career and now I am a photographer."}); query="What is my current job?"; expected_response_contains=@("photographer"); expected_memory_excludes=@("programmer"); require_all_contains=$true; require_all_excludes=$true},
  @{test_id="upd_002"; type="update"; description="city update"; turns=@(@{role="user"; content="I live in Shanghai."},@{role="user"; content="I moved to Beijing."}); query="Where do I live now?"; expected_response_contains=@("Beijing"); expected_memory_excludes=@("Shanghai"); require_all_contains=$true; require_all_excludes=$true},
  @{test_id="upd_003"; type="update"; description="diet update"; turns=@(@{role="user"; content="I am vegetarian."},@{role="user"; content="I now eat meat again."}); query="What is my current diet?"; expected_response_contains=@("eat meat"); expected_memory_excludes=@("vegetarian"); require_all_contains=$false; require_all_excludes=$true},
  @{test_id="upd_004"; type="update"; description="allergy update"; turns=@(@{role="user"; content="I am allergic to shrimp."},@{role="user"; content="I am no longer allergic to shrimp, but allergic to mango now."}); query="What am I currently allergic to?"; expected_response_contains=@("mango"); expected_memory_excludes=@("shrimp"); require_all_contains=$true; require_all_excludes=$true},
  @{test_id="upd_005"; type="update"; description="pet update"; turns=@(@{role="user"; content="I had a dog named Dahuang."},@{role="user"; content="Now I have a ragdoll cat named Snowball."}); query="What pet do I have now?"; expected_response_contains=@("Snowball","cat"); expected_memory_excludes=@("Dahuang"); require_all_contains=$false; require_all_excludes=$true}
)

for ($i=6; $i -le 30; $i++) {
  $n = '{0:d3}' -f $i
  $oldJob = @("programmer","product manager","operations","teacher","reporter")[$i % 5]
  $newJob = @("photographer","designer","consultant","translator","data scientist")[$i % 5]
  $oldCity = @("Guangzhou","Xiamen","Tianjin","Ningbo","Fuzhou")[$i % 5]
  $newCity = @("Beijing","Shanghai","Shenzhen","Hangzhou","Chengdu")[$i % 5]
  $update += @{
    test_id = "upd_$n"
    type = "update"
    description = "batch update case_$n"
    turns = @(
      @{role="user"; content="I previously worked as a $oldJob in $oldCity."},
      @{role="user"; content="Recently I moved to $newCity and changed career to $newJob."}
    )
    query = "Which city am I in now and what is my job now?"
    expected_response_contains = @($newCity, $newJob)
    expected_memory_excludes = @($oldCity, $oldJob)
    require_all_contains = $false
    require_all_excludes = $true
  }
}
$update | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $root "update_tests.json") -Encoding utf8

$e = (Get-Content (Join-Path $root "extraction_tests.json") -Raw | ConvertFrom-Json).Count
$r = (Get-Content (Join-Path $root "retrieval_tests.json") -Raw | ConvertFrom-Json).Count
$u = (Get-Content (Join-Path $root "update_tests.json") -Raw | ConvertFrom-Json).Count
Write-Host "counts => extraction:$e retrieval:$r update:$u"