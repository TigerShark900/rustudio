
undefined8 FUN_143eedb80(undefined8 param_1)

{
  int iVar1;
  longlong lVar2;
  int iVar3;
  int *piVar4;
  undefined8 uVar5;

  piVar4 = (int *)FUN_143d82f90();
  iVar1 = *piVar4;
  lVar2 = *(longlong *)(piVar4 + 2);
  iVar3 = func_0x000143145a30(param_1);
  if (iVar3 < 1) {
    FUN_142aee720(0,&UNK_14910c548,iVar1);
  }
  else {
    uVar5 = FUN_1431494b0(param_1,0xffffffff);
    FUN_142aee720(0,&UNK_14910c540,uVar5,iVar1);
  }
  if ((iVar1 == 5) && (lVar2 != 0)) {
    FUN_142aee720(0,&UNK_14910c560);
  }
  return 0;
}
