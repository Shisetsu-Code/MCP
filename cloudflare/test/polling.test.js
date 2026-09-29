import {test} from 'node:test';
import assert from 'node:assert/strict';
import {pollDelay,waitBudget} from '../src/polling.js';
test('bounded backoff avoids 250 reads for a 25 second wait',()=>{
  let elapsed=0,reads=0;
  while(elapsed<25000) {elapsed+=pollDelay(reads++,25000-elapsed);}
  assert.ok(reads<=17);
  assert.equal(pollDelay(0,25000),100);
  assert.equal(pollDelay(10,25000),2000);
  assert.equal(pollDelay(10,50),50);
});
test('zero wait remains zero and invalid budgets use the default',()=>{
  assert.equal(waitBudget(0,12000),0);
  assert.equal(waitBudget('invalid',12000),12000);
  assert.equal(waitBudget(50000,12000),25000);
});
