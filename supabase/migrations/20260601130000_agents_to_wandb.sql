-- Migrate the council entirely to W&B Inference open models (no Anthropic).
-- Backfills already-seeded agents in place; new/generated agents default to
-- W&B in code (schemas.AgentCreate, org_builder, persona frontmatter).
-- A diverse flagship per named persona; everything else -> gpt-oss-120b.
update public.agents
set provider = 'wandb',
    model = case
      when name ilike 'Nicolas%' then 'moonshotai/Kimi-K2.6'
      when name ilike 'Ra%ad%'   then 'Qwen/Qwen3-235B-A22B-Instruct-2507'
      when name ilike 'Ryan%'    then 'deepseek-ai/DeepSeek-V4-Pro'
      when name ilike '%Skeptic%' then 'openai/gpt-oss-120b'
      when name ilike 'Uma%'     then 'zai-org/GLM-5.1'
      else 'openai/gpt-oss-120b'
    end
where provider <> 'wandb' or model not like '%/%';
