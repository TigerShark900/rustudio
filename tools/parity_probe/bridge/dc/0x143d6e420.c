
undefined8 FUN_143d6e420(undefined8 param_1)

{
  code *pcVar1;
  int iVar2;
  undefined8 uVar3;
  longlong lVar4;
  
  uVar3 = FUN_14314ce10(param_1,2);
  lVar4 = FUN_142ab05c0(uVar3);
  if (lVar4 != 0) {
    FUN_143d6e9c0(param_1,lVar4);
    return 1;
  }
  iVar2 = func_0x0001478c035c(uVar3,&UNK_1490eede8);
  if (iVar2 == 0) {
    FUN_143146a90(param_1,FUN_143d6eaa0,&UNK_1490eede8,0,0);
    return 1;
  }
  FUN_143a7c550(&UNK_1490eedf8,uVar3);
  pcVar1 = (code *)swi(3);
  uVar3 = (*pcVar1)();
  return uVar3;
}

